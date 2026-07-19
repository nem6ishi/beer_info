"""
LLM-based enrichment command.
Extracts brewery and beer names using a specified LLM provider (Gemini, Local MLX, etc).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, cast, Tuple

from ..core.db import get_supabase_client, refresh_materialized_view, sync_execute
from ..core.types import GeminiExtraction
from ..services.llm import BaseExtractor, get_llm_extractor
from ..services.store.brewery_manager import BreweryManager
from .failure_tracker import record_enrichment_failure

logger: logging.Logger = logging.getLogger(__name__)

class LLMEnricher:
    """Encapsulates the LLM extraction process and its state."""

    def __init__(
        self,
        offline: bool = False,
        force_reprocess: bool = False,
        shop_filter: Optional[str] = None,
        keyword_filter: Optional[str] = None,
        llm_provider: str = "gemini",
        llm_model_id: Optional[str] = None,
    ):
        self.offline = offline
        self.force_reprocess = force_reprocess
        self.shop_filter = shop_filter
        self.keyword_filter = keyword_filter
        
        self.supabase: Any = get_supabase_client()
        self.extractor: BaseExtractor = get_llm_extractor(provider=llm_provider, model_id=llm_model_id)
        self.brewery_manager: BreweryManager = BreweryManager()

        self.stats: Dict[str, int] = {"processed": 0, "enriched": 0, "errors": 0}
        self.pending_payloads: List[Dict[str, Any]] = []

    async def run(self, limit: int = 50) -> None:
        """Runs the enrichment pipeline up to the specified limit."""
        logger.info("=" * 70)
        logger.info(f"🤖 LLM Extraction ({self.extractor.__class__.__name__})")
        if self.offline:
            logger.info("📴 OFFLINE MODE: Skipping LLM calls.")
        logger.info("=" * 70)

        if not self.offline and not getattr(self.extractor, 'client', True) and getattr(self.extractor, 'model', True) is None:
            logger.warning("\n⚠️ Warning: No valid LLM client found, might fail depending on provider")
        
        logger.info(f"📚 Loaded {len(self.brewery_manager.breweries)} known breweries as hints")
        
        total_remaining: int = self._get_count()
        logger.info(f"📊 Total items needing enrichment: {total_remaining}")
        
        if total_remaining == 0:
            logger.info("✨ No items need enrichment. Exiting.")
            return

        while self.stats["processed"] < limit:
            remaining: int = limit - self.stats["processed"]
            batch_size: int = min(100, remaining)

            logger.info(f"\n📂 Loading candidates (Batch Target: {batch_size})...")
            beers: List[Dict[str, Any]] = self._fetch_candidates(self.stats["processed"], batch_size)
            
            if not beers:
                logger.info("\n✨ No more beers found matching criteria!")
                break
                
            for beer in beers:
                if self.stats["processed"] >= limit:
                    break
                
                status, payload = await self._process_item(beer)
                
                self.stats["processed"] += 1
                if status == 'enriched' and payload:
                    self.stats["enriched"] += 1
                    self.pending_payloads.append(payload)
                elif status == 'already_exists':
                    self.stats["enriched"] += 1
                elif status == 'error':
                    self.stats["errors"] += 1

            if self.pending_payloads:
                self._save_gemini_data_batch(self.pending_payloads)
                self.pending_payloads.clear()
                if not self.offline and self.supabase:
                    refresh_materialized_view(self.supabase, logger)

        # Save any remaining payloads that haven't been committed
        if self.pending_payloads:
            self._save_gemini_data_batch(self.pending_payloads)
            self.pending_payloads.clear()

        self._print_final_report()
        if not self.offline:
            refresh_materialized_view(self.supabase, logger)

    def _get_count(self) -> int:
        """Gets total count of items requiring enrichment."""
        query: Any = self.supabase.table('beer_info_view').select('url', count='exact', head=True)
        query = self._apply_filters(query)
        res: Any = sync_execute(query)
        return cast(int, res.count)

    def _fetch_candidates(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """Fetches a batch of candidate beers."""
        query: Any = self.supabase.table('beer_info_view').select('*')
        query = self._apply_filters(query)
        response: Any = sync_execute(query.order('first_seen', desc=True).limit(limit).offset(offset))
        return cast(List[Dict[str, Any]], response.data or [])

    def _apply_filters(self, query: Any) -> Any:
        """Applies common filters to a query."""
        if self.offline:
            query = query.not_.is_('brewery_name_en', 'null').is_('untappd_url', 'null')
        elif not self.force_reprocess:
            query = query.or_(
                'brewery_name_en.is.null,'
                'untappd_url.is.null,'
                'untappd_url.ilike.%/search?%'
            )

        if self.shop_filter:
            query = query.eq('shop', self.shop_filter)
        if self.keyword_filter:
            query = query.ilike('name', f'%{self.keyword_filter}%')
        return query

    async def _process_item(self, beer: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Processes a single beer item: Extract and prepare payload."""
        has_names: bool = bool(beer.get('brewery_name_en') and beer.get('beer_name_en'))
        has_hint: bool = bool(beer.get('search_hint'))
        need_gemini: bool = self.force_reprocess or not has_names or not has_hint
        
        url: str = beer.get('url', '')
        if not url: return 'skipped', None
        
        try:
            if need_gemini:
                if self.offline:
                    logger.info("  ⏭️ LLM extraction needed but skipped in offline mode.")
                    return 'skipped', None
                
                # Extract
                enriched_info: Optional[GeminiExtraction] = await self._extract_llm(beer)
                if not enriched_info:
                    record_enrichment_failure(self.supabase, url, 'gemini_no_info', error_message="LLM returned no valid info.")
                    return 'error', None
                
                # Self-Healing Dictionary Feedback Loop
                b_en = enriched_info.get('brewery_name_en')
                b_jp = enriched_info.get('brewery_name_jp')
                if b_en and b_jp:
                    self.brewery_manager.learn_brewery_alias(brewery_name_en=b_en, new_alias=b_jp)

                # Prepare payload
                payload: Dict[str, Any] = {
                    'url': url,
                    'brewery_name_en': b_en,
                    'brewery_name_jp': b_jp,
                    'beer_name_en': enriched_info.get('beer_name_en'),
                    'beer_name_jp': enriched_info.get('beer_name_jp'),
                    'beer_name_core': enriched_info.get('beer_name_core'),
                    'search_hint': enriched_info.get('search_hint'),
                    'product_type': enriched_info.get('product_type', 'beer'),
                    'is_set': enriched_info.get('is_set', False),
                    'payload': enriched_info.get('raw_response'),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                return 'enriched', payload
                
            else:
                logger.info(f"  ⏩ Extracted data already exists. Skipping extraction. (Brewery: {beer.get('brewery_name_en')})")
                return 'already_exists', None

        except Exception as e:
            logger.error(f"  ❌ Error processing item: {e}")
            record_enrichment_failure(self.supabase, url, 'gemini_error', error_message=str(e))
            return 'error', None

    async def _extract_llm(self, beer: Dict[str, Any]) -> Optional[GeminiExtraction]:
        """Helper to get hints and call LLM."""
        known_brewery: Optional[str] = None
        beer_name: str = beer.get('name') or ""
        matches: List[Dict[str, Any]] = self.brewery_manager.find_breweries_in_text(beer_name)
        
        if matches:
            known_brewery = ", ".join([b['name_en'] for b in matches])
            logger.info(f"  🏭 Known brewery hints: {known_brewery}")
        
        logger.info("  🤖 Calling LLM Extractor...")
        return await self.extractor.extract_info(beer_name, known_brewery=known_brewery, shop=beer.get('shop'))

    def _save_gemini_data_batch(self, payloads: List[Dict[str, Any]]) -> None:
        """Helper to save a batch of enriched data to Supabase."""
        if not payloads:
            return
        
        try:
            sync_execute(self.supabase.table('gemini_data').upsert(payloads))
            logger.info(f"  💾 Saved {len(payloads)} items to gemini_data")
        except Exception as e:
            if 'beer_name_core' in str(e) or 'search_hint' in str(e) or 'column' in str(e).lower():
                logger.warning(f"  ⚠️ New columns not in DB yet, trying to save without search hints")
                cleaned_payloads = []
                for p in payloads:
                    cp = p.copy()
                    cp.pop('beer_name_core', None)
                    cp.pop('search_hint', None)
                    cleaned_payloads.append(cp)
                try:
                    sync_execute(self.supabase.table('gemini_data').upsert(cleaned_payloads))
                    logger.info(f"  💾 Saved {len(cleaned_payloads)} items to gemini_data (fallback)")
                except Exception as inner_e:
                    logger.error(f"  ❌ Error in gemini_data fallback upsert: {inner_e}")
                    raise
            else:
                logger.error(f"  ❌ Error in gemini_data upsert: {e}")
                raise

        # Resolve previous failures in batch
        urls = [p['url'] for p in payloads]
        try:
            res = sync_execute(self.supabase.table('untappd_search_failures').update({'resolved': True}).in_('product_url', urls).eq('resolved', False))
            if res.data:
                logger.info(f"  🔄 Resolved {len(res.data)} previous Untappd search failures for this batch.")
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to resolve previous search failures: {e}")



    def _print_final_report(self) -> None:
        """Prints a summary of the enrichment run."""
        logger.info(f"\n{'='*70}\n📈 Final Statistics\n{'='*70}")
        logger.info(f"  Total processed: {self.stats['processed']}")
        logger.info(f"  LLM extracted: {self.stats['enriched']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"\n  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}\n✨ LLM extraction completed!\n{'='*70}")


async def enrich_extract(
    limit: int = 50, 
    shop_filter: Optional[str] = None, 
    keyword_filter: Optional[str] = None, 
    offline: bool = False, 
    force_reprocess: bool = False,
    llm_provider: str = "gemini",
    llm_model_id: Optional[str] = None
) -> None:
    """
    Entry point: Extract beers using the specified LLM.
    """
    enricher = LLMEnricher(
        offline=offline,
        force_reprocess=force_reprocess,
        shop_filter=shop_filter,
        keyword_filter=keyword_filter,
        llm_provider=llm_provider,
        llm_model_id=llm_model_id
    )
    await enricher.run(limit=limit)

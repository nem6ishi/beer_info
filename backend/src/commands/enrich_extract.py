"""
LLM-based enrichment command.
Extracts brewery and beer names using a specified LLM provider (Gemini, Local MLX, etc).
"""
"""
Enrichment Phase 1: LLM Extraction

This module is responsible for fetching raw beer strings from the database (scraped_beers)
and using an LLM (Gemini or Local MLX) to extract structured data such as:
- brewery_name_en (English Brewery Name)
- beer_name_en (English Beer Name)
- search_hint (Optimized string for searching Untappd)

The extracted results are saved to the `gemini_data` table for the next phase.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, cast, Tuple, Set

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
        retry_unlinked: bool = False,
    ):
        self.offline = offline
        self.force_reprocess = force_reprocess
        self.retry_unlinked = retry_unlinked
        self.shop_filter = shop_filter
        self.keyword_filter = keyword_filter
        
        self.supabase: Any = get_supabase_client()
        self.extractor: BaseExtractor = get_llm_extractor(provider=llm_provider, model_id=llm_model_id)
        self.brewery_manager: BreweryManager = BreweryManager()

        self.stats: Dict[str, int] = {"processed": 0, "enriched": 0, "errors": 0, "api_errors": 0}
        self.pending_payloads: List[Dict[str, Any]] = []
        self.skip_urls_for_backoff: Set[str] = set()
        self.consecutive_api_errors: int = 0
        self.max_consecutive_api_errors: int = 5
        self._fresh_exhausted: bool = False

    def _preload_failure_history(self) -> None:
        """Pre-loads failure records so backoff-eligible URLs are skipped during LLM extraction."""
        if self.force_reprocess or self.keyword_filter or self.offline:
            return
        try:
            from dateutil import parser as dateutil_parser
            cutoff: datetime = datetime.now(timezone.utc) - timedelta(days=3)
            page_size: int = 1000
            page_offset: int = 0
            while True:
                res: Any = self.supabase.table('untappd_search_failures') \
                    .select('product_url, search_attempts, last_failed_at') \
                    .eq('resolved', False) \
                    .order('id') \
                    .range(page_offset, page_offset + page_size - 1) \
                    .execute()
                rows = res.data or []
                for f in rows:
                    p_url = f.get('product_url', '')
                    if not p_url:
                        continue
                    if f.get('search_attempts', 0) >= 3:
                        self.skip_urls_for_backoff.add(p_url)
                    elif f.get('last_failed_at'):
                        try:
                            if dateutil_parser.parse(f['last_failed_at']) > cutoff:
                                self.skip_urls_for_backoff.add(p_url)
                        except Exception:
                            pass
                if len(rows) < page_size:
                    break
                page_offset += page_size
            if self.skip_urls_for_backoff:
                logger.info(f"  ⏭️ Loaded {len(self.skip_urls_for_backoff)} backoff URLs to skip in LLM extraction.")
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to preload failure history: {e}")

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
        self._preload_failure_history()
        
        total_remaining: int = self._get_count()
        logger.info(f"📊 Total items needing enrichment: {total_remaining}")
        
        if total_remaining == 0:
            logger.info("✨ No items need enrichment. Exiting.")
            return

        fresh_offset: int = 0
        view_offset: int = 0
        self._fresh_exhausted = False
        circuit_broken: bool = False
        while self.stats["processed"] < limit and not circuit_broken:
            remaining: int = limit - self.stats["processed"]
            batch_size: int = min(100, remaining)

            if not self._fresh_exhausted:
                logger.info(f"\n📂 Loading fresh candidates (Batch Target: {batch_size}, Offset: {fresh_offset})...")
                raw_beers: List[Dict[str, Any]] = self._fetch_candidates(fresh_offset, batch_size, source='fresh')
                if raw_beers:
                    fresh_offset += len(raw_beers)
                else:
                    self._fresh_exhausted = True
                    continue
            else:
                logger.info(f"\n📂 Loading view candidates (Batch Target: {batch_size}, Offset: {view_offset})...")
                raw_beers = self._fetch_candidates(view_offset, batch_size, source='view')
                if not raw_beers:
                    logger.info("\n✨ No more beers found matching criteria!")
                    break
                view_offset += len(raw_beers)

            beers: List[Dict[str, Any]] = [
                b for b in raw_beers if b.get('url') not in self.skip_urls_for_backoff
            ]
            if not beers:
                logger.info(f"  ⏭️ All {len(raw_beers)} fetched candidates are in backoff. Continuing to next page...")
                continue
                
            for beer in beers:
                if self.stats["processed"] >= limit:
                    break
                
                status, payload = await self._process_item(beer)
                
                self.stats["processed"] += 1
                if status == 'enriched' and payload:
                    self.consecutive_api_errors = 0
                    self.stats["enriched"] += 1
                    self.pending_payloads.append(payload)
                    if len(self.pending_payloads) >= 10:
                        self._save_gemini_data_batch(self.pending_payloads)
                        self.pending_payloads.clear()
                elif status == 'already_exists':
                    self.consecutive_api_errors = 0
                    self.stats["enriched"] += 1
                elif status == 'api_error':
                    self.stats["api_errors"] += 1
                    self.consecutive_api_errors += 1
                    if self.consecutive_api_errors >= self.max_consecutive_api_errors:
                        logger.warning(
                            f"  🛑 Circuit breaker triggered: {self.consecutive_api_errors} consecutive LLM API errors. "
                            f"Aborting remaining batch to avoid polluting failure logs."
                        )
                        circuit_broken = True
                        break
                elif status == 'error':
                    self.consecutive_api_errors = 0
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
        # 1. Fresh unenriched items in scraped_beers
        sb_query: Any = self.supabase.table('scraped_beers').select('url', count='exact', head=True).neq('stock_status', 'Dead Link').is_('untappd_enriched_at', 'null')
        if self.shop_filter:
            sb_query = sb_query.eq('shop', self.shop_filter)
        if self.keyword_filter:
            sb_query = sb_query.ilike('name', f'%{self.keyword_filter}%')
        sb_res: Any = sync_execute(sb_query)
        fresh_count: int = cast(int, sb_res.count or 0)
        if fresh_count > 0:
            return fresh_count

        # 2. Existing items in view
        query: Any = self.supabase.table('beer_info_view').select('url', count='exact', head=True)
        query = self._apply_filters(query)
        res: Any = sync_execute(query)
        return cast(int, res.count or 0)

    def _fetch_candidates(self, offset: int, limit: int, source: str = 'auto') -> List[Dict[str, Any]]:
        """Fetches a batch of candidate beers."""
        if source in ('auto', 'fresh'):
            # Check if there are fresh items directly from scraped_beers (In Stock first)
            sb_query: Any = self.supabase.table('scraped_beers') \
                .select('url, name, shop, untappd_url, first_seen, stock_status') \
                .neq('stock_status', 'Dead Link') \
                .is_('untappd_enriched_at', 'null')
            if self.shop_filter:
                sb_query = sb_query.eq('shop', self.shop_filter)
            if self.keyword_filter:
                sb_query = sb_query.ilike('name', f'%{self.keyword_filter}%')
            sb_res: Any = sync_execute(
                sb_query.order('stock_status', desc=False).order('first_seen', desc=True).limit(limit).offset(offset)
            )
            fresh_items: List[Dict[str, Any]] = cast(List[Dict[str, Any]], sb_res.data or [])

            if fresh_items:
                fresh_urls = [b['url'] for b in fresh_items if b.get('url')]
                g_map: Dict[str, Any] = {}
                if fresh_urls:
                    try:
                        g_res = self.supabase.table('gemini_data') \
                            .select('url, brewery_name_en, beer_name_en') \
                            .in_('url', fresh_urls).execute()
                        g_map = {r['url']: r for r in (g_res.data or [])}
                    except Exception as e:
                        logger.warning(f"  ⚠️ Error fetching gemini_data: {e}")
                for b in fresh_items:
                    g_info = g_map.get(b['url'], {})
                    b['brewery_name_en'] = g_info.get('brewery_name_en')
                    b['beer_name_en'] = g_info.get('beer_name_en')
                return fresh_items
            if source == 'fresh':
                return []

        # Otherwise query existing view (prioritize 'In Stock' before 'Sold Out' via alphabetical order)
        query: Any = self.supabase.table('beer_info_view').select(
            'url, name, shop, brewery_name_en, beer_name_en, untappd_url, stock_status'
        )
        query = self._apply_filters(query)
        response: Any = sync_execute(
            query.order('stock_status', desc=False).order('first_seen', desc=True).limit(limit).offset(offset)
        )
        return cast(List[Dict[str, Any]], response.data or [])

    def _apply_filters(self, query: Any) -> Any:
        """Applies common filters to a query."""
        if self.offline:
            query = query.not_.is_('brewery_name_en', 'null').is_('untappd_url', 'null')
        elif self.retry_unlinked:
            query = query.is_('untappd_url', 'null')
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
        is_unlinked: bool = not bool(beer.get('untappd_url'))
        need_gemini: bool = self.force_reprocess or (self.retry_unlinked and is_unlinked) or not has_names
        
        url: str = beer.get('url', '')
        if not url: return 'skipped', None
        
        try:
            if need_gemini:
                if self.offline:
                    logger.info("  ⏭️ LLM extraction needed but skipped in offline mode.")
                    return 'skipped', None
                
                # Extract
                enriched_info: Optional[GeminiExtraction] = await self._extract_llm(beer)
                if enriched_info and enriched_info.get('_api_error'):
                    err_msg = enriched_info.get('_error_message', 'Transient LLM API error')
                    logger.warning(f"  ⚠️ Transient LLM API error (skipping failure record so item can retry): {err_msg}")
                    return 'api_error', None

                has_extracted_content = bool(
                    enriched_info and (
                        enriched_info.get('brewery_name_en') or
                        enriched_info.get('beer_name_en') or
                        enriched_info.get('brewery_name_jp') or
                        enriched_info.get('beer_name_jp') or
                        enriched_info.get('product_type', 'beer') != 'beer' or
                        enriched_info.get('is_set')
                    )
                )
                if not enriched_info or not has_extracted_content:
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
    retry_unlinked: bool = False,
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
        llm_model_id=llm_model_id,
        retry_unlinked=retry_unlinked
    )
    await enricher.run(limit=limit)

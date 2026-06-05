"""
Gemini-only enrichment command.
Extracts brewery and beer names using Gemini API.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, cast, Tuple

from ..core.db import get_supabase_client
from ..core.types import GeminiExtraction
from ..services.gemini.extractor import GeminiExtractor
from ..services.store.brewery_manager import BreweryManager
from .failure_tracker import record_enrichment_failure

logger: logging.Logger = logging.getLogger(__name__)

class GeminiEnricher:
    """Encapsulates the Gemini enrichment process and its state."""

    def __init__(
        self,
        offline: bool = False,
        force_reprocess: bool = False,
        shop_filter: Optional[str] = None,
        keyword_filter: Optional[str] = None,
    ):
        self.offline = offline
        self.force_reprocess = force_reprocess
        self.shop_filter = shop_filter
        self.keyword_filter = keyword_filter
        
        self.supabase: Any = get_supabase_client()
        self.extractor: GeminiExtractor = GeminiExtractor()
        self.brewery_manager: BreweryManager = BreweryManager()

        self.stats: Dict[str, int] = {"processed": 0, "enriched": 0, "errors": 0}
        self.pending_payloads: List[Dict[str, Any]] = []

    async def run(self, limit: int = 50) -> None:
        """Runs the enrichment pipeline up to the specified limit."""
        logger.info("=" * 70)
        logger.info("🤖 Gemini Enrichment (Supabase)")
        if self.offline:
            logger.info("📴 OFFLINE MODE: Skipping API calls.")
        logger.info("=" * 70)

        if not self.offline and not self.extractor.client:
            logger.error("\n❌ Error: Gemini API key not configured")
            return
        
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
                
            sem = asyncio.Semaphore(5)
            
            async def _process_with_sem(beer: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
                async with sem:
                    return await self._process_item(beer)
                    
            tasks = [_process_with_sem(beer) for beer in beers]
            results = await asyncio.gather(*tasks)
            
            for beer, (status, payload) in zip(beers, results):
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

        # Save any remaining payloads that haven't been committed
        if self.pending_payloads:
            self._save_gemini_data_batch(self.pending_payloads)
            self.pending_payloads.clear()

        self._print_final_report()
        if not self.offline:
            self._refresh_materialized_view()

    def _get_count(self) -> int:
        """Gets total count of items requiring enrichment."""
        query: Any = self.supabase.table('beer_info_view').select('url', count='exact', head=True)
        query = self._apply_filters(query)
        res: Any = query.execute()
        return cast(int, res.count)

    def _fetch_candidates(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """Fetches a batch of candidate beers."""
        query: Any = self.supabase.table('beer_info_view').select('*')
        query = self._apply_filters(query)
        response: Any = query.order('first_seen', desc=True).limit(limit).offset(offset).execute()
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
                    logger.info("  ⏭️ Gemini enrichment needed but skipped in offline mode.")
                    return 'skipped', None
                
                # Extract
                enriched_info: Optional[GeminiExtraction] = await self._extract_gemini(beer)
                if not enriched_info:
                    record_enrichment_failure(self.supabase, url, 'gemini_no_info', error_message="Gemini returned no valid info.")
                    return 'error', None
                
                # Prepare payload
                payload: Dict[str, Any] = {
                    'url': url,
                    'brewery_name_en': enriched_info.get('brewery_name_en'),
                    'brewery_name_jp': enriched_info.get('brewery_name_jp'),
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
                logger.info(f"  ⏩ Gemini data already exists. Skipping extraction. (Brewery: {beer.get('brewery_name_en')})")
                return 'already_exists', None

        except Exception as e:
            logger.error(f"  ❌ Error processing item: {e}")
            record_enrichment_failure(self.supabase, url, 'gemini_error', error_message=str(e))
            return 'error', None

    async def _extract_gemini(self, beer: Dict[str, Any]) -> Optional[GeminiExtraction]:
        """Helper to get hints and call Gemini."""
        known_brewery: Optional[str] = None
        beer_name: str = beer.get('name') or ""
        matches: List[Dict[str, Any]] = self.brewery_manager.find_breweries_in_text(beer_name)
        
        if matches:
            known_brewery = ", ".join([b['name_en'] for b in matches])
            logger.info(f"  🏭 Known brewery hints: {known_brewery}")
        
        logger.info("  🤖 Calling Gemini API...")
        return await self.extractor.extract_info(beer_name, known_brewery=known_brewery, shop=beer.get('shop'))

    def _save_gemini_data_batch(self, payloads: List[Dict[str, Any]]) -> None:
        """Helper to save a batch of enriched data to Supabase."""
        if not payloads:
            return
        
        try:
            self.supabase.table('gemini_data').upsert(payloads).execute()
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
                    self.supabase.table('gemini_data').upsert(cleaned_payloads).execute()
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
            res = self.supabase.table('untappd_search_failures').update({'resolved': True}).in_('product_url', urls).eq('resolved', False).execute()
            if res.data:
                logger.info(f"  🔄 Resolved {len(res.data)} previous Untappd search failures for this batch.")
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to resolve previous search failures: {e}")

    def _refresh_materialized_view(self) -> None:
        logger.info("\n🔄 Refreshing Materialized View (beer_info_view)...")
        try:
            self.supabase.rpc('refresh_beer_info_view').execute()
            logger.info("✅ View refreshed successfully!")
        except Exception as e:
            logger.warning(f"⚠️ Failed to refresh view: {e}")

    def _print_final_report(self) -> None:
        """Prints a summary of the enrichment run."""
        logger.info(f"\n{'='*70}\n📈 Final Statistics\n{'='*70}")
        logger.info(f"  Total processed: {self.stats['processed']}")
        logger.info(f"  Gemini enriched: {self.stats['enriched']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info(f"\n  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*70}\n✨ Gemini enrichment completed!\n{'='*70}")


async def enrich_gemini(
    limit: int = 50, 
    shop_filter: Optional[str] = None, 
    keyword_filter: Optional[str] = None, 
    offline: bool = False, 
    force_reprocess: bool = False
) -> None:
    """
    Entry point: Enrich beers with Gemini extraction only.
    """
    enricher = GeminiEnricher(
        offline=offline,
        force_reprocess=force_reprocess,
        shop_filter=shop_filter,
        keyword_filter=keyword_filter
    )
    await enricher.run(limit=limit)

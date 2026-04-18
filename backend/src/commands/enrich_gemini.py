"""
Gemini-only enrichment command.
Extracts brewery and beer names using Gemini API.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Set, cast

from ..core.db import get_supabase_client
from ..core.config import settings
from ..core.types import GeminiExtraction
from ..services.gemini.extractor import GeminiExtractor
from ..services.store.brewery_manager import BreweryManager
from .failure_tracker import record_enrichment_failure

logger: logging.Logger = logging.getLogger(__name__)

async def enrich_gemini(
    limit: int = 50, 
    shop_filter: Optional[str] = None, 
    keyword_filter: Optional[str] = None, 
    offline: bool = False, 
    force_reprocess: bool = False
) -> None:
    """
    Enrich beers with Gemini extraction only.
    """
    logger.info("=" * 70)
    logger.info("🤖 Gemini Enrichment (Supabase)")
    if offline:
        logger.info("📴 OFFLINE MODE: Skipping API calls.")
    logger.info("=" * 70)
    
    supabase: Any = get_supabase_client()
    extractor: GeminiExtractor = GeminiExtractor()
    if not offline and not extractor.client:
        logger.error("\n❌ Error: Gemini API key not configured")
        return
    
    brewery_manager: BreweryManager = BreweryManager()
    logger.info(f"📚 Loaded {len(brewery_manager.breweries)} known breweries as hints")
    
    total_remaining: int = _get_count(supabase, shop_filter, keyword_filter, offline, force_reprocess)
    logger.info(f"📊 Total items needing enrichment: {total_remaining}")
    
    if total_remaining == 0:
        logger.info("✨ No items need enrichment. Exiting.")
        return

    stats: Dict[str, int] = {"processed": 0, "enriched": 0, "errors": 0}
    
    while stats["processed"] < limit:
        remaining: int = limit - stats["processed"]
        batch_size: int = min(100, remaining)

        logger.info(f"\n📂 Loading candidates (Batch Target: {batch_size})...")
        beers: List[Dict[str, Any]] = _fetch_candidates(supabase, stats["processed"], batch_size, shop_filter, keyword_filter, offline, force_reprocess)
        
        if not beers:
            logger.info("\n✨ No more beers found matching criteria!")
            break
            
        for beer in beers:
            stats["processed"] += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"[Item {stats['processed']}/{limit}] Processing: {beer.get('name', 'Unknown')[:60]}")
            logger.info(f"{'='*70}")
            
            success: Optional[bool] = await _process_item(supabase, extractor, brewery_manager, beer, offline, force_reprocess)
            if success:
                stats["enriched"] += 1
            elif success is None:
                stats["errors"] += 1

    _print_final_report(stats)

def _get_count(supabase: Any, shop: Optional[str], keyword: Optional[str], offline: bool, force: bool) -> int:
    """Gets total count of items requiring enrichment."""
    query: Any = supabase.table('beer_info_view').select('count', count='exact', head=True)
    query = _apply_filters(query, shop, keyword, offline, force)
    res: Any = query.execute()
    return cast(int, res.count)

def _fetch_candidates(supabase: Any, offset: int, limit: int, shop: Optional[str], keyword: Optional[str], offline: bool, force: bool) -> List[Dict[str, Any]]:
    """Fetches a batch of candidate beers."""
    query: Any = supabase.table('beer_info_view').select('*')
    query = _apply_filters(query, shop, keyword, offline, force)
    response: Any = query.order('first_seen', desc=True).limit(limit).offset(offset).execute()
    return cast(List[Dict[str, Any]], response.data or [])

def _apply_filters(query: Any, shop: Optional[str], keyword: Optional[str], offline: bool, force: bool) -> Any:
    """Applies common filters to a query."""
    if offline:
        query = query.not_.is_('brewery_name_en', 'null').is_('untappd_url', 'null')
    elif not force:
        query = query.or_(
            'brewery_name_en.is.null,'
            'untappd_url.is.null,'
            'untappd_url.ilike.%/search?%,'
            'search_hint.is.null'
        )

    if shop:
        query = query.eq('shop', shop)
    if keyword:
        query = query.ilike('name', f'%{keyword}%')
    return query


async def _process_item(
    supabase: Any, 
    extractor: GeminiExtractor, 
    brewery_manager: BreweryManager, 
    beer: Dict[str, Any], 
    offline: bool, 
    force: bool
) -> Optional[bool]:
    """Processes a single beer item: Extract -> Save."""
    has_names: bool = bool(beer.get('brewery_name_en') and beer.get('beer_name_en'))
    has_hint: bool = bool(beer.get('search_hint'))
    need_gemini: bool = force or not has_names or not has_hint
    
    url: str = beer.get('url', '')
    if not url: return False
    
    try:
        if need_gemini:
            if offline:
                logger.info("  ⏭️ Gemini enrichment needed but skipped in offline mode.")
                return False
            
            # Extract
            enriched_info: Optional[GeminiExtraction] = await _extract_gemini(extractor, brewery_manager, beer)
            if not enriched_info:
                record_enrichment_failure(supabase, url, 'gemini_no_info', "Gemini returned no valid info.")
                return False
            
            # Save
            _save_gemini_data(supabase, url, enriched_info)
            
        else:
            logger.info(f"  ⏩ Gemini data already exists. Skipping extraction. (Brewery: {beer.get('brewery_name_en')})")
            
        return True

    except Exception as e:
        logger.error(f"  ❌ Error processing item: {e}")
        record_enrichment_failure(supabase, url, 'gemini_error', str(e))
        return None

async def _extract_gemini(extractor: GeminiExtractor, brewery_manager: BreweryManager, beer: Dict[str, Any]) -> Optional[GeminiExtraction]:
    """Helper to get hints and call Gemini."""
    known_brewery: Optional[str] = None
    beer_name: str = beer.get('name') or ""
    matches: List[Dict[str, Any]] = brewery_manager.find_breweries_in_text(beer_name)
    if matches:
        known_brewery = ", ".join([b['name_en'] for b in matches])
        logger.info(f"  🏭 Known brewery hints: {known_brewery}")
    
    logger.info("  🤖 Calling Gemini API...")
    return await extractor.extract_info(beer_name, known_brewery=known_brewery, shop=beer.get('shop'))

def _save_gemini_data(supabase: Any, url: str, info: GeminiExtraction) -> None:
    """Helper to save enriched data to Supabase."""
    payload: Dict[str, Any] = {
        'url': url,
        'brewery_name_en': info.get('brewery_name_en'),
        'brewery_name_jp': info.get('brewery_name_jp'),
        'beer_name_en': info.get('beer_name_en'),
        'beer_name_jp': info.get('beer_name_jp'),
        'beer_name_core': info.get('beer_name_core'),
        'search_hint': info.get('search_hint'),
        'product_type': info.get('product_type', 'beer'),
        'is_set': info.get('is_set', False),
        'payload': info.get('raw_response'),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    try:
        supabase.table('gemini_data').upsert(payload).execute()
    except Exception as e:
        if 'beer_name_core' in str(e) or 'search_hint' in str(e) or 'column' in str(e).lower():
            logger.warning(f"  ⚠️ New columns not in DB yet, saving without search hints (run migration 005)")
            payload.pop('beer_name_core', None)
            payload.pop('search_hint', None)
            supabase.table('gemini_data').upsert(payload).execute()
        else:
            raise

    logger.info(f"  💾 Saved to gemini_data (Type: {payload.get('product_type')})")

def _print_final_report(stats: Dict[str, int]) -> None:
    """Prints a summary of the enrichment run."""
    logger.info(f"\n{'='*70}\n📈 Final Statistics\n{'='*70}")
    logger.info(f"  Total processed: {stats['processed']}")
    logger.info(f"  Gemini enriched: {stats['enriched']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info(f"\n  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'='*70}\n✨ Gemini enrichment completed!\n{'='*70}")

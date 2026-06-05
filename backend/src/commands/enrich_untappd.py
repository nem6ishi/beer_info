"""
Untappd-only enrichment command.
Enriches beers with Untappd data.
Modes:
- missing: Finds Untappd URLs for beers that don't have one.
- refresh: Updates details (rating, ABV, etc.) for beers that already have a URL.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set

from backend.src.core.db import get_supabase_client
from backend.src.core.types import UntappdBeerDetails, UntappdSearchResult
from backend.src.services.untappd.searcher import get_untappd_url, scrape_beer_details
from backend.src.services.gemini.extractor import GeminiExtractor
from backend.src.services.store.brewery_manager import BreweryManager
from backend.src.commands.failure_tracker import record_enrichment_failure, resolve_search_failure

logger: logging.Logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_numeric(val: Optional[str]) -> Optional[float]:
    """Helper to parse numeric values from strings."""
    if not val:
        return None
    try:
        # Remove non-numeric characters except dots
        clean = re.sub(r'[^0-9.]', '', str(val))
        return float(clean) if clean else None
    except Exception:
        return None

def map_details_to_payload(details: UntappdBeerDetails) -> Dict[str, Any]:
    """Maps scraper keys to untappd_data table columns."""
    return {
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': details.get('untappd_brewery_name'),
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'abv_num': parse_numeric(details.get('untappd_abv')),
        'ibu': details.get('untappd_ibu'),
        'ibu_num': parse_numeric(details.get('untappd_ibu')),
        'rating': details.get('untappd_rating'),
        'rating_num': parse_numeric(details.get('untappd_rating')),
        'rating_count': details.get('untappd_rating_count'),
        'rating_count_num': parse_numeric(details.get('untappd_rating_count')),
        'image_url': details.get('untappd_label'),
        'untappd_brewery_url': details.get('untappd_brewery_url'),
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }


def _get_brewery_url_hint(brewery: str, brewery_manager: Optional[BreweryManager]) -> Optional[str]:
    """Looks up the known Untappd brewery URL from BreweryManager."""
    if not brewery_manager or not brewery:
        return None
    try:
        b_info: Optional[Dict[str, Any]] = brewery_manager.brewery_index.get(brewery.lower())
        if b_info:
            url: Optional[str] = b_info.get('untappd_url')
            if url:
                logger.info(f"  🏢 Known brewery URL: {url}")
                return url
    except Exception as e:
        logger.warning(f"  ⚠️  BreweryManager lookup failed: {e}")
    return None


async def _resolve_untappd_url(
    beer: Dict[str, Any],
    brewery: str,
    beer_name: str,
    brewery_url_hint: Optional[str],
    extractor: Optional[GeminiExtractor],
    gemini_cache: Dict[str, str],
) -> Optional[str]:
    """
    Core URL resolution logic:
    1. Check persistence in gemini_cache (pre-loaded)
    2. Search Untappd with all fallback strategies
    3. Two-pass retry via Gemini if no_results
    Returns the resolved URL, or None if not found.
    """
    supabase: Any = get_supabase_client()
    untappd_url: Optional[str] = beer.get('untappd_url')
    url: Optional[str] = beer.get('url')

    # 1. Check persistence in gemini_cache
    if not untappd_url and url:
        p_url = gemini_cache.get(url)
        if p_url and '/search?' not in p_url:
            logger.info(f"  ✅ [Persistence] Found link in gemini_cache: {p_url}")
            return p_url

    if untappd_url and '/search?' not in untappd_url:
        return untappd_url

    # 2. Search Untappd
    beer_name_jp: Optional[str] = beer.get('beer_name_jp')
    search_hint: Optional[str] = beer.get('search_hint')
    beer_name_core: Optional[str] = beer.get('beer_name_core')

    logger.info(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
    search_result: UntappdSearchResult = get_untappd_url(
        brewery, beer_name,
        beer_name_jp=beer_name_jp,
        brewery_url=brewery_url_hint,
        search_hint=search_hint,
        beer_name_core=beer_name_core
    )

    # 3. Two-pass retry: ask Gemini for alternative queries
    if not search_result.get('success') and search_result.get('failure_reason') == 'no_results' and extractor:
        logger.info(f"  🔄 [Two-pass] Asking Gemini for alternative queries...")
        try:
            full_name: str = beer.get('name', '')
            alt_queries: List[str] = await extractor.suggest_search_queries(
                product_name=full_name,
                brewery=brewery,
                beer_name=beer_name
            )
            for alt_query in alt_queries:
                logger.info(f"  🔍 [Two-pass] Trying: '{alt_query}'")
                retry_result: UntappdSearchResult = get_untappd_url(
                    brewery_name=brewery,
                    beer_name=beer_name,
                    search_hint=alt_query,
                    beer_name_core=beer_name_core
                )
                if retry_result.get('success'):
                    logger.info(f"  ✅ [Two-pass] Found: {retry_result.get('url')}")
                    return retry_result.get('url')
                await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"  ⚠️ [Two-pass] Gemini retry failed: {e}")

    # Record failure
    if not search_result.get('success'):
        if url:
            record_enrichment_failure(
                supabase,
                product_url=url,
                brewery_name=brewery,
                beer_name=beer_name,
                beer_name_jp=beer_name_jp,
                failure_reason=search_result.get('failure_reason', 'unknown'),
                error_message=search_result.get('error_message') or "Unknown error"
            )
        if search_result.get('failure_reason') == 'no_results':
            logger.info(f"  ⏭️  No direct link found. Failure recorded.")
            return None

    return search_result.get('url')


async def _scrape_and_save_details(
    untappd_url: str, 
    beer: Dict[str, Any], 
    brewery: str, 
    beer_name: str,
    untappd_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Scrapes beer details and returns untappd_payload. Returns {} if nothing to save."""
    supabase: Any = get_supabase_client()
    url: str = beer.get('url', '')

    # Check if details already exist in local cache
    if untappd_url in untappd_cache:
        logger.info(f"  💾 Data already exists in untappd_cache. Linking only.")
        return {}

    if "untappd.com/b/" not in untappd_url:
        return {}

    await asyncio.sleep(2)  # Rate limiting
    logger.info(f"  🔄 Scraping beer details...")
    details: UntappdBeerDetails = scrape_beer_details(untappd_url)
    if details:
        payload: Dict[str, Any] = map_details_to_payload(details)
        payload['untappd_url'] = untappd_url
        logger.info(f"  ✅ Details scraped: {details.get('untappd_style', 'N/A')}")
        
        # Add to local cache for subsequent items in this batch
        untappd_cache[untappd_url] = {
            'untappd_url': untappd_url,
            'untappd_brewery_url': details.get('untappd_brewery_url')
        }
        return payload
    else:
        logger.warning(f"  ⚠️  Could not scrape details")
        if url:
            record_enrichment_failure(
                supabase,
                product_url=url,
                brewery_name=brewery,
                beer_name=beer_name,
                failure_reason='untappd_scrape_error',
                error_message="Failed to scrape details from Untappd page."
            )
        return {'untappd_url': untappd_url, 'fetched_at': datetime.now(timezone.utc).isoformat()}


def commit_updates_batch(
    supabase: Any,
    untappd_payloads: List[Dict[str, Any]],
    gemini_updates: List[Dict[str, Any]],
    scraped_updates: List[Dict[str, Any]],
) -> None:
    """Commits all accumulated updates to the database in batch."""
    if untappd_payloads:
        try:
            supabase.table('untappd_data').upsert(untappd_payloads).execute()
            logger.info(f"  💾 Saved {len(untappd_payloads)} items to untappd_data (Batch)")
        except Exception as e:
            logger.error(f"  ❌ Error saving to untappd_data (Batch): {e}")

    if gemini_updates:
        try:
            supabase.table('gemini_data').upsert(gemini_updates).execute()
            logger.info(f"  💾 Saved {len(gemini_updates)} items to gemini_data (Batch)")
        except Exception as e:
            logger.error(f"  ⚠️ Error updating gemini_data (Batch): {e}")

    if scraped_updates:
        try:
            supabase.table('scraped_beers').upsert(scraped_updates).execute()
            logger.info(f"  💾 Linked {len(scraped_updates)} items in scraped_beers (Batch)")
        except Exception as e:
            logger.error(f"  ❌ Error updating scraped_beers (Batch): {e}")


async def process_beer_missing(
    beer: Dict[str, Any], 
    brewery_manager: Optional[BreweryManager] = None, 
    extractor: Optional[GeminiExtractor] = None, 
    offline: bool = False,
    gemini_cache: Optional[Dict[str, str]] = None,
    untappd_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Process a beer in 'missing' mode.
    """
    brewery: Optional[str] = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name: Optional[str] = beer.get('beer_name_en') or beer.get('beer_name_jp')
    product_type: Optional[str] = beer.get('product_type')
    url: Optional[str] = beer.get('url')

    if product_type and product_type != 'beer':
        logger.info(f"  ⏭️ Item is a {product_type}. Skipping Untappd.")
        return None

    if (not brewery or not beer_name) and beer.get('shop') == "ちょうせいや":
        match: Optional[re.Match] = re.search(r'【(.*?)/(.*?)】', beer.get('name', ''))
        if match:
            beer_name, brewery = match.group(1), match.group(2)
            logger.info(f"  🔧 Parsed from title: {brewery} - {beer_name}")

    if not brewery or not beer_name:
        logger.warning(f"  ⚠️  Missing brewery or beer name - skipping")
        return None

    supabase: Any = get_supabase_client()

    try:
        brewery_url_hint: Optional[str] = _get_brewery_url_hint(brewery, brewery_manager)
        untappd_url: Optional[str] = None

        if offline:
            logger.info(f"  🔍 [Offline] Searching DB for: {brewery} - {beer_name}")
            db_res: Any = supabase.table('untappd_data').select('untappd_url') \
                .ilike('beer_name', beer_name) \
                .ilike('brewery_name', f"%{brewery}%") \
                .limit(1).execute()
            if db_res.data:
                untappd_url = db_res.data[0]['untappd_url']
                logger.info(f"  ✅ [Offline] Found in DB: {untappd_url}")
            else:
                logger.info(f"  ⏭️  [Offline] Not found in DB. Skipping.")
                return None
        else:
            untappd_url = await _resolve_untappd_url(beer, brewery, beer_name, brewery_url_hint, extractor, gemini_cache or {})

        if not untappd_url:
            return None

        scraped_updates: Dict[str, Any] = {'url': url, 'untappd_url': untappd_url}
        gemini_updates: Dict[str, Any] = {'url': url, 'untappd_url': untappd_url}

        logger.info(f"  ✅ Found URL: {untappd_url}")
        if url:
            resolve_search_failure(supabase, url)

        untappd_payload: Dict[str, Any] = {}
        if not offline:
            untappd_payload = await _scrape_and_save_details(untappd_url, beer, brewery, beer_name, untappd_cache or {})
            if untappd_payload:
                untappd_payload['untappd_url'] = untappd_url

        brewery_url_to_return = untappd_payload.get('untappd_brewery_url')
        if not brewery_url_to_return and untappd_cache and untappd_url in untappd_cache:
            brewery_url_to_return = untappd_cache[untappd_url].get('untappd_brewery_url')

        return {
            'untappd_payload': untappd_payload,
            'gemini_payload': gemini_updates,
            'scraped_payload': scraped_updates,
            'untappd_brewery_url': brewery_url_to_return
        }

    except Exception as e:
        logger.error(f"  ❌ Untappd search error: {e}")
        return None


async def process_beer_refresh(
    beer: Dict[str, Any],
    untappd_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Process a beer in 'refresh' mode: re-scrape details for existing URLs."""
    untappd_url: Optional[str] = beer.get('untappd_url')
    if not untappd_url or "untappd.com/b/" not in untappd_url:
        logger.warning(f"  ⚠️  Invalid Untappd URL: {untappd_url}")
        return None

    logger.info(f"  🔄 Refreshing: {beer.get('beer_name', 'Unknown')} ({untappd_url})")

    try:
        await asyncio.sleep(2)
        details: UntappdBeerDetails = scrape_beer_details(untappd_url)
        untappd_payload: Dict[str, Any]
        if details:
            untappd_payload = map_details_to_payload(details)
            untappd_payload['untappd_url'] = untappd_url
            logger.info(f"  ✅ Details updated: Rating {details.get('untappd_rating', 'N/A')}")
            
            if untappd_cache:
                untappd_cache[untappd_url] = {
                    'untappd_url': untappd_url,
                    'untappd_brewery_url': details.get('untappd_brewery_url')
                }
        else:
            logger.warning(f"  ⚠️  Could not scrape details")
            untappd_payload = {'untappd_url': untappd_url, 'fetched_at': datetime.now(timezone.utc).isoformat()}
        
        return {
            'untappd_payload': untappd_payload,
            'gemini_payload': {},
            'scraped_payload': {},
            'untappd_brewery_url': untappd_payload.get('untappd_brewery_url')
        }
    except Exception as e:
        logger.error(f"  ❌ Refresh error: {e}")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

async def enrich_untappd(
    limit: int = 50,
    mode: str = 'missing',
    shop_filter: Optional[str] = None,
    name_filter: Optional[str] = None
) -> Set[str]:
    """
    Enrich beers with Untappd data.
    Returns set of brewery URLs found/updated.
    """
    logger.info("=" * 70)
    logger.info(f"🍺 Untappd Enrichment (Mode: {mode.upper()})")
    if shop_filter:
        logger.info(f"🏪 Shop Filter: {shop_filter}")
    if name_filter:
        logger.info(f"🔍 Name Filter: {name_filter}")
    logger.info("=" * 70)
    logger.info(f"Batch size: {limit}")

    supabase: Any = get_supabase_client()

    # ── Instantiate shared dependencies ONCE ──────────────────────────────────
    brewery_manager: Optional[BreweryManager] = None
    extractor: Optional[GeminiExtractor] = None
    if mode == 'missing':
        try:
            brewery_manager = BreweryManager()
            logger.info(f"  🏢 BreweryManager loaded ({len(brewery_manager.brewery_index)} breweries)")
        except Exception as e:
            logger.warning(f"  ⚠️  BreweryManager unavailable: {e}")

        try:
            extractor = GeminiExtractor()
            logger.info(f"  🤖 GeminiExtractor loaded (for Two-pass retry)")
        except Exception as e:
            logger.warning(f"  ⚠️  GeminiExtractor unavailable: {e}")

    total_processed: int = 0
    total_success: int = 0
    collected_brewery_urls: Set[str] = set()
    processed_this_run: Set[str] = set()
    
    # Pre-load failure records for backoff
    skip_urls_for_backoff: Set[str] = set()
    if mode == 'missing':
        logger.info("  🔍 Pre-loading failure history for backoff filtering...")
        from dateutil import parser as dateutil_parser
        cutoff: datetime = datetime.now(timezone.utc) - timedelta(days=3)
        failure_res: Any = supabase.table('untappd_search_failures') \
            .select('product_url, search_attempts, last_failed_at') \
            .eq('resolved', False) \
            .execute()
        for f in (failure_res.data or []):
            attempts: int = f.get('search_attempts', 0)
            last_failed_str: Optional[str] = f.get('last_failed_at')
            p_url: str = f.get('product_url', '')
            if attempts >= 3:
                skip_urls_for_backoff.add(p_url)
            elif last_failed_str:
                try:
                    last_failed: datetime = dateutil_parser.parse(last_failed_str)
                    if last_failed > cutoff:
                        skip_urls_for_backoff.add(p_url)
                except Exception:
                    pass
        if skip_urls_for_backoff:
            logger.info(f"  ⏭️ {len(skip_urls_for_backoff)} URLs will be skipped due to backoff policy.")

    offset: int = 0
    db_fetch_limit: int = 200

    while True:
        beers: List[Dict[str, Any]] = []

        if mode == 'missing':
            query: Any = supabase.table('beer_info_view') \
                .select('*') \
                .or_('untappd_url.is.null,untappd_url.ilike.%/search?%') \
                .eq('product_type', 'beer')
            if shop_filter:
                query = query.eq('shop', shop_filter)
            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')
            res: Any = query.order('first_seen', desc=True).limit(db_fetch_limit).offset(offset).execute()
            beers = res.data or []
            
            if skip_urls_for_backoff:
                beers = [b for b in beers if b.get('url') not in skip_urls_for_backoff]

        elif mode == 'refresh':
            logger.info(f"\n📂 Loading batch of REFRESH beers (offset={offset})...")
            cutoff_date: str = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            query = supabase.table('beer_info_view') \
                .select('url, name, untappd_url, stock_status, untappd_fetched_at') \
                .not_.is_('untappd_url', 'null') \
                .neq('stock_status', 'Sold Out') \
                .or_(f'untappd_fetched_at.is.null,untappd_fetched_at.lt.{cutoff_date}')
            if shop_filter:
                query = query.eq('shop', shop_filter)
            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')
            res = query.order('untappd_fetched_at', desc=False, nullsfirst=True).limit(db_fetch_limit).offset(offset).execute()
            beers = res.data or []

        offset += db_fetch_limit
        beers = [b for b in beers if b.get('url') not in processed_this_run]

        remaining_capacity: int = limit - total_processed
        beers_to_process: List[Dict[str, Any]] = beers[:remaining_capacity]

        logger.info(f"  Valid {len(beers_to_process)} beers to process in this batch")
        if not beers_to_process:
            logger.info("\n✨ No more beers to process!")
            break

        # ── Prefetch Caches for the current batch to avoid DB N+1 ───────────────
        urls_to_process = [b.get('url') for b in beers_to_process if b.get('url')]
        
        gemini_cache: Dict[str, str] = {}
        if urls_to_process:
            try:
                gemini_res = supabase.table('gemini_data').select('url, untappd_url').in_('url', urls_to_process).execute()
                gemini_cache = {item['url']: item.get('untappd_url') for item in (gemini_res.data or []) if item.get('untappd_url')}
            except Exception as e:
                logger.warning(f"  ⚠️ Failed to prefetch gemini_data cache: {e}")

        known_untappd_urls = []
        for b in beers_to_process:
            u_url = b.get('untappd_url')
            if u_url and '/search?' not in u_url:
                known_untappd_urls.append(u_url)
            else:
                g_url = gemini_cache.get(b.get('url'))
                if g_url and '/search?' not in g_url:
                    known_untappd_urls.append(g_url)

        untappd_cache: Dict[str, Dict[str, Any]] = {}
        if known_untappd_urls:
            try:
                untappd_res = supabase.table('untappd_data').select('untappd_url, untappd_brewery_url').in_('untappd_url', known_untappd_urls).execute()
                untappd_cache = {item['untappd_url']: item for item in (untappd_res.data or [])}
            except Exception as e:
                logger.warning(f"  ⚠️ Failed to prefetch untappd_data cache: {e}")

        # Accumulating payloads
        batch_untappd = []
        batch_gemini = []
        batch_scraped = []

        for i, beer in enumerate(beers_to_process, 1):
            product_url_loop: Optional[str] = beer.get('url')
            if not product_url_loop:
                continue
            processed_this_run.add(product_url_loop)

            name_display: str = beer.get('name', beer.get('beer_name', 'Unknown'))
            logger.info(f"\n{'='*70}")
            logger.info(f"[Batch {i}/{len(beers_to_process)} | Total {total_processed + i}] Processing: {name_display[:60]}")
            logger.info(f"{'='*70}")

            result: Optional[Dict[str, Any]] = None
            if mode == 'missing':
                result = await process_beer_missing(beer, brewery_manager=brewery_manager, extractor=extractor, gemini_cache=gemini_cache, untappd_cache=untappd_cache)
            elif mode == 'refresh':
                result = await process_beer_refresh(beer, untappd_cache=untappd_cache)

            if result:
                total_success += 1
                b_url = result.get('untappd_brewery_url')
                if b_url:
                    collected_brewery_urls.add(b_url)
                
                if result.get('untappd_payload'):
                    batch_untappd.append(result['untappd_payload'])
                if result.get('gemini_payload') and result['gemini_payload'].get('url'):
                    batch_gemini.append(result['gemini_payload'])
                if result.get('scraped_payload') and result['scraped_payload'].get('url'):
                    batch_scraped.append(result['scraped_payload'])

            await asyncio.sleep(1)

        # Commit batch
        if batch_untappd or batch_gemini or batch_scraped:
            commit_updates_batch(supabase, batch_untappd, batch_gemini, batch_scraped)

        total_processed += len(beers_to_process)
        if total_processed >= limit:
            break

    logger.info(f"\n{'='*70}")
    logger.info("✨ Untappd enrichment completed!")
    logger.info(f"{'='*70}")
    return list(collected_brewery_urls)


"""
Untappd-only enrichment command.
Enriches beers with Untappd data.
Modes:
- missing: Finds Untappd URLs for beers that don't have one.
- refresh: Updates details (rating, ABV, etc.) for beers that already have a URL.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from backend.src.core.db import get_supabase_client
from backend.src.services.untappd.searcher import get_untappd_url, scrape_beer_details, UntappdBeerDetails, UntappdSearchResult
from backend.src.commands.failure_tracker import record_enrichment_failure, resolve_search_failure

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def map_details_to_payload(details: UntappdBeerDetails) -> dict:
    """Maps scraper keys to untappd_data table columns."""
    return {
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': details.get('untappd_brewery_name'),
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'ibu': details.get('untappd_ibu'),
        'rating': details.get('untappd_rating'),
        'rating_count': details.get('untappd_rating_count'),
        'image_url': details.get('untappd_label'),
        'untappd_brewery_url': details.get('untappd_brewery_url'),
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }


def _get_brewery_url_hint(brewery: str, brewery_manager) -> Optional[str]:
    """Looks up the known Untappd brewery URL from BreweryManager."""
    if not brewery_manager or not brewery:
        return None
    try:
        b_info = brewery_manager.brewery_index.get(brewery.lower())
        if b_info:
            url = b_info.get('untappd_url')
            if url:
                logger.info(f"  🏢 Known brewery URL: {url}")
                return url
    except Exception as e:
        logger.warning(f"  ⚠️  BreweryManager lookup failed: {e}")
    return None


async def _resolve_untappd_url(
    beer: dict,
    brewery: str,
    beer_name: str,
    brewery_url_hint: Optional[str],
    extractor,
) -> Optional[str]:
    """
    Core URL resolution logic:
    1. Check persistence in gemini_data
    2. Search Untappd with all fallback strategies
    3. Two-pass retry via Gemini if no_results
    Returns the resolved URL, or None if not found.
    """
    supabase = get_supabase_client()
    untappd_url = beer.get('untappd_url')

    # 1. Check persistence in gemini_data
    if not untappd_url and beer.get('url'):
        try:
            res = supabase.table('gemini_data').select('untappd_url').eq('url', beer['url']).execute()
            if res.data and res.data[0].get('untappd_url'):
                p_url = res.data[0]['untappd_url']
                if '/search?' not in p_url:
                    logger.info(f"  ✅ [Persistence] Found link in gemini_data: {p_url}")
                    return p_url
        except Exception as e:
            logger.warning(f"  ⚠️ Error checking persistence: {e}")

    if untappd_url and '/search?' not in untappd_url:
        return untappd_url

    # 2. Search Untappd
    beer_name_jp = beer.get('beer_name_jp')
    search_hint = beer.get('search_hint')
    beer_name_core = beer.get('beer_name_core')

    logger.info(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
    search_result = get_untappd_url(
        brewery, beer_name,
        beer_name_jp=beer_name_jp,
        brewery_url=brewery_url_hint,
        search_hint=search_hint,
        beer_name_core=beer_name_core
    )

    # 3. Two-pass retry: ask Gemini for alternative queries
    if not search_result.get('success') and search_result.get('failure_reason') == 'no_results' and beer.get('name'):
        logger.info(f"  🔄 [Two-pass] Asking Gemini for alternative queries...")
        try:
            alt_queries = await extractor.suggest_search_queries(
                product_name=beer.get('name', ''),
                brewery=brewery,
                beer_name=beer_name
            )
            for alt_query in alt_queries:
                logger.info(f"  🔍 [Two-pass] Trying: '{alt_query}'")
                retry_result = get_untappd_url(
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
        if beer.get('url'):
            record_enrichment_failure(
                supabase,
                product_url=beer['url'],
                brewery_name=brewery,
                beer_name=beer_name,
                beer_name_jp=beer_name_jp,
                failure_reason=search_result.get('failure_reason', 'unknown'),
                error_message=search_result.get('error_message')
            )
        if search_result.get('failure_reason') == 'no_results':
            logger.info(f"  ⏭️  No direct link found. Failure recorded.")
            return None

    return search_result.get('url')


async def _scrape_and_save_details(untappd_url: str, beer: dict, brewery: str, beer_name: str) -> dict:
    """Scrapes beer details and returns untappd_payload. Returns {} if nothing to save."""
    supabase = get_supabase_client()

    # Check if details already exist
    existing = supabase.table('untappd_data').select('untappd_url, fetched_at').eq('untappd_url', untappd_url).execute()
    if existing.data:
        logger.info(f"  💾 Data already exists in untappd_data. Linking only.")
        return {}

    if "untappd.com/b/" not in untappd_url:
        return {}

    await asyncio.sleep(2)  # Rate limiting
    logger.info(f"  🔄 Scraping beer details...")
    details = scrape_beer_details(untappd_url)
    if details:
        payload = map_details_to_payload(details)
        payload['untappd_url'] = untappd_url
        logger.info(f"  ✅ Details scraped: {details.get('untappd_style', 'N/A')}")
        return payload
    else:
        logger.warning(f"  ⚠️  Could not scrape details")
        record_enrichment_failure(
            supabase,
            product_url=beer.get('url', ''),
            brewery_name=brewery,
            beer_name=beer_name,
            failure_reason='untappd_scrape_error',
            error_message="Failed to scrape details from Untappd page."
        )
        return {'untappd_url': untappd_url, 'fetched_at': datetime.now(timezone.utc).isoformat()}


async def commit_updates(beer: dict, untappd_payload: dict, gemini_updates: dict, scraped_updates: dict) -> dict:
    """Commits all updates to the database."""
    supabase = get_supabase_client()
    success = False

    if untappd_payload:
        try:
            supabase.table('untappd_data').upsert(untappd_payload).execute()
            logger.info(f"  💾 Saved to untappd_data")
            success = True
        except Exception as e:
            logger.error(f"  ❌ Error saving to untappd_data: {e}")

    if gemini_updates and beer.get('url'):
        try:
            supabase.table('gemini_data').update(gemini_updates).eq('url', beer['url']).execute()
            logger.info(f"  💾 Persisted URL to gemini_data")
        except Exception as e:
            logger.error(f"  ⚠️ Error updating gemini_data: {e}")

    if scraped_updates and beer.get('url'):
        try:
            supabase.table('scraped_beers').update(scraped_updates).eq('url', beer['url']).execute()
            logger.info(f"  🔗 Linked scraping_beers")
            success = True
        except Exception as e:
            logger.error(f"  ❌ Error updating scraped_beers: {e}")

    return untappd_payload or scraped_updates


# ── Main processing functions ─────────────────────────────────────────────────

async def process_beer_missing(beer: dict, brewery_manager=None, extractor=None, offline: bool = False):
    """
    Process a beer in 'missing' mode.
    brewery_manager and extractor are passed in to avoid re-instantiation per beer.
    """
    # Extract brewery and beer names
    brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')

    if beer.get('product_type') and beer.get('product_type') != 'beer':
        logger.info(f"  ⏭️ Item is a {beer.get('product_type')}. Skipping Untappd.")
        return None

    if not brewery or not beer_name:
        import re
        match = re.search(r'【(.*?)/(.*?)】', beer.get('name', ''))
        if match:
            beer_name, brewery = match.group(1), match.group(2)
            logger.info(f"  🔧 Parsed from title: {brewery} - {beer_name}")

    if not brewery or not beer_name:
        logger.warning(f"  ⚠️  Missing brewery or beer name - skipping")
        return None

    supabase = get_supabase_client()

    try:
        brewery_url_hint = _get_brewery_url_hint(brewery, brewery_manager)
        untappd_url = None

        if offline:
            # Offline mode: search DB only
            logger.info(f"  🔍 [Offline] Searching DB for: {brewery} - {beer_name}")
            db_res = supabase.table('untappd_data').select('untappd_url') \
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
            untappd_url = await _resolve_untappd_url(beer, brewery, beer_name, brewery_url_hint, extractor)

        if not untappd_url:
            return None

        scraped_updates = {'untappd_url': untappd_url}
        gemini_updates = {'untappd_url': untappd_url}

        logger.info(f"  ✅ Found URL: {untappd_url}")
        if beer.get('url'):
            resolve_search_failure(supabase, beer['url'])

        if offline:
            untappd_payload = {}
        else:
            untappd_payload = await _scrape_and_save_details(untappd_url, beer, brewery, beer_name)
            if untappd_payload:
                untappd_payload['untappd_url'] = untappd_url

        return await commit_updates(beer, untappd_payload, gemini_updates, scraped_updates)

    except Exception as e:
        logger.error(f"  ❌ Untappd search error: {e}")
        return None


async def process_beer_refresh(beer: dict, brewery_manager=None, extractor=None):
    """Process a beer in 'refresh' mode: re-scrape details for existing URLs."""
    untappd_url = beer.get('untappd_url')
    if not untappd_url or "untappd.com/b/" not in untappd_url:
        logger.warning(f"  ⚠️  Invalid Untappd URL: {untappd_url}")
        return None

    logger.info(f"  🔄 Refreshing: {beer.get('beer_name', 'Unknown')} ({untappd_url})")

    try:
        await asyncio.sleep(2)
        details = scrape_beer_details(untappd_url)
        if details:
            untappd_payload = map_details_to_payload(details)
            untappd_payload['untappd_url'] = untappd_url
            logger.info(f"  ✅ Details updated: Rating {details.get('untappd_rating', 'N/A')}")
        else:
            logger.warning(f"  ⚠️  Could not scrape details")
            untappd_payload = {'untappd_url': untappd_url, 'fetched_at': datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error(f"  ❌ Refresh error: {e}")
        return None

    return await commit_updates(beer, untappd_payload, {}, {})


# ── Main entry point ──────────────────────────────────────────────────────────

async def enrich_untappd(
    limit: int = 50,
    mode: str = 'missing',
    shop_filter: str = None,
    name_filter: str = None
) -> List[str]:
    """
    Enrich beers with Untappd data.
    BreweryManager and GeminiExtractor are instantiated ONCE and shared across all beers.
    """
    logger.info("=" * 70)
    logger.info(f"🍺 Untappd Enrichment (Mode: {mode.upper()})")
    if shop_filter:
        logger.info(f"🏪 Shop Filter: {shop_filter}")
    if name_filter:
        logger.info(f"🔍 Name Filter: {name_filter}")
    logger.info("=" * 70)
    logger.info(f"Batch size: {limit}")

    supabase = get_supabase_client()

    # ── Instantiate shared dependencies ONCE ──────────────────────────────────
    brewery_manager = None
    extractor = None
    if mode == 'missing':
        try:
            from backend.src.services.store.brewery_manager import BreweryManager
            brewery_manager = BreweryManager()
            logger.info(f"  🏢 BreweryManager loaded ({len(brewery_manager.brewery_index)} breweries)")
        except Exception as e:
            logger.warning(f"  ⚠️  BreweryManager unavailable: {e}")

        try:
            from backend.src.services.gemini.extractor import GeminiExtractor
            extractor = GeminiExtractor()
            logger.info(f"  🤖 GeminiExtractor loaded (for Two-pass retry)")
        except Exception as e:
            logger.warning(f"  ⚠️  GeminiExtractor unavailable: {e}")

    total_processed = 0
    total_success = 0
    batch_size = min(limit, 1000)
    collected_brewery_urls: set = set()

    while True:
        beers = []

        if mode == 'missing':
            query = supabase.table('beer_info_view') \
                .select('*') \
                .or_('untappd_url.is.null,untappd_url.ilike.%/search?%') \
                .eq('product_type', 'beer')
            if shop_filter:
                query = query.eq('shop', shop_filter)
            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')
            beers = query.order('first_seen', desc=True).limit(batch_size).execute().data

        elif mode == 'refresh':
            logger.info(f"\n📂 Loading batch of REFRESH beers (Limit: {batch_size})...")
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            query = supabase.table('beer_info_view') \
                .select('url, name, untappd_url, stock_status, untappd_fetched_at') \
                .not_.is_('untappd_url', None) \
                .neq('stock_status', 'Sold Out') \
                .or_(f'untappd_fetched_at.is.null,untappd_fetched_at.lt.{cutoff_date}')
            if shop_filter:
                query = query.eq('shop', shop_filter)
            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')
            beers = query.order('untappd_fetched_at', desc=False, nullsfirst=True).limit(batch_size).execute().data

        logger.info(f"  Found {len(beers)} beers to process")
        if not beers:
            logger.info("\n✨ No more beers to process!")
            break

        processed_urls: set = set()
        for i, beer in enumerate(beers, 1):
            product_url = beer.get('url')
            if product_url in processed_urls:
                continue
            processed_urls.add(product_url)

            name_display = beer.get('name', beer.get('beer_name', 'Unknown'))
            logger.info(f"\n{'='*70}")
            logger.info(f"[Batch {i}/{len(beers)} | Total {total_processed + i}] Processing: {name_display[:60]}")
            logger.info(f"{'='*70}")

            result = None
            if mode == 'missing':
                result = await process_beer_missing(beer, brewery_manager=brewery_manager, extractor=extractor)
            elif mode == 'refresh':
                result = await process_beer_refresh(beer)

            if result:
                total_success += 1
                if isinstance(result, dict):
                    b_url = result.get('untappd_brewery_url')
                    if b_url:
                        collected_brewery_urls.add(b_url)

            await asyncio.sleep(1)

        total_processed += len(beers)
        if total_processed >= limit:
            break

    logger.info(f"\n{'='*70}")
    logger.info("✨ Untappd enrichment completed!")
    logger.info(f"{'='*70}")
    return list(collected_brewery_urls)

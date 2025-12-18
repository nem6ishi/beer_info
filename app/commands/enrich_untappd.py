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
from typing import List, Set, Optional

from app.core.db import get_supabase_client
from app.services.untappd.searcher import get_untappd_url, scrape_beer_details, UntappdBeerDetails

logger = logging.getLogger(__name__)

def map_details_to_payload(details: UntappdBeerDetails):
    """Maps scraper keys to untappd_data table columns."""
    return {
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': details.get('untappd_brewery_name'),
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'ibu': details.get('untappd_ibu'),
        'rating': details.get('untappd_rating'),
        'rating_count': details.get('untappd_rating_count'),
        'image_url': details.get('untappd_label'), # Map 'untappd_label' -> 'image_url'
        'untappd_brewery_url': details.get('untappd_brewery_url'), # Map brewery URL
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }


async def process_beer_missing(beer: dict, offline: bool = False):
    """
    Process a beer in 'missing' mode:
    1. Check if URL exists in untappd_data already.
    2. Search Untappd (Web or Local DB).
    3. If found, save URL and scrape details.
    """
    supabase = get_supabase_client()
    scraped_updates = {} # Updates for scraped_beers table (link)
    untappd_payload = {} # Updates for untappd_data table (master info)
    gemini_updates = {}  # Updates for gemini_data table (persistence)
    
    # Extract brewery and beer names
    brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
    
    if beer.get('is_set'):
        logger.info(f"  📦 Item is a Set/Merch. Skipping Untappd.")
        return None

    if not brewery or not beer_name:
        import re
        match = re.search(r'【(.*?)/(.*?)】', beer.get('name', ''))
        if match:
             beer_name = match.group(1)
             brewery = match.group(2)
             logger.info(f"  🔧 Parsed from title: {brewery} - {beer_name}")
    
    if not brewery or not beer_name:
        logger.warning(f"  ⚠️  Missing brewery or beer name - skipping")
        return None
    
    try:
        untappd_url = beer.get('untappd_url')
        
        # 1. Check persistence in gemini_data (if we've linked this URL before)
        if not untappd_url and beer.get('url'):
            try:
                persistence = supabase.table('gemini_data').select('untappd_url').eq('url', beer['url']).maybe_single().execute()
                if persistence.data and persistence.data.get('untappd_url'):
                    p_url = persistence.data['untappd_url']
                    if '/search?' not in p_url:
                        untappd_url = p_url
                        logger.info(f"  ✅ [Persistence] Found link in gemini_data: {untappd_url}")
                    else:
                        logger.info(f"  🔄 [Persistence] Found search URL in gemini_data, will re-search: {p_url}")
            except Exception as e:
                logger.error(f"  ⚠️ Error checking persistence: {e}")

        # Try to find known brewery URL for priority search
        brewery_url_hint = None
        if brewery:
            # We use a simple global cache for BreweryManager to avoid reloading for every beer
            # Note: In command structure we might want a cleaner way, but keeping logic similar for now.
            # Local import to avoid circular dep if BreweryManager uses this file someday (unlikely but safe)
            from app.services.store.brewery_manager import BreweryManager
            try:
                # Ideally pass manager in, but for now instantiate
                bm = BreweryManager() 
                # Note: This loads DB every time if not careful. 
                # Script logic used a global. Let's try to simulate that or just instantiate.
                # Since BreweryManager loads on init, we should instantiate ONCE in the main loop and pass it down?
                # For `process_beer_missing` meant to be standalone-ish helper, maybe just load index?
                # Optimization: The original script used a global `_brewery_manager`. 
                # We can do the same within the module scope if needed, or better, pass context.
                # For now, let's just allow re-instantiation overhead or rely on it being fast enough, 
                # OR simpler: check simple aliases.
                # Actually, let's keep it simple:
                b_info = bm.brewery_index.get(brewery.lower())
                if b_info:
                    brewery_url_hint = b_info.get('untappd_url')
                    if brewery_url_hint:
                         logger.info(f"  🏢 Known brewery URL found: {brewery_url_hint}")
            except Exception as e:
                logger.warning(f"  ⚠️  Could not load BreweryManager: {e}")

        # Search if no URL found yet
        if not untappd_url:
            if offline:
                logger.info(f"  🔍 [Offline] Searching DB for: {brewery} - {beer_name}")
                query = supabase.table('untappd_data').select('untappd_url').ilike('beer_name', beer_name)
                
                passed_brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
                if passed_brewery:
                     query = query.ilike('brewery_name', f"%{passed_brewery}%")
                
                db_res = query.limit(1).execute()
                
                if db_res.data:
                    untappd_url = db_res.data[0]['untappd_url']
                    logger.info(f"  ✅ [Offline] Found in DB: {untappd_url}")
                else:
                    logger.info(f"  ⏭️  [Offline] Not found in DB. Skipping.")
                    return None
            else:
                logger.info(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
                beer_name_jp_clean = beer.get('beer_name_jp')
                untappd_url = get_untappd_url(brewery, beer_name, beer_name_jp=beer_name_jp_clean, brewery_url=brewery_url_hint)
        
        if untappd_url:
            scraped_updates['untappd_url'] = untappd_url
            gemini_updates['untappd_url'] = untappd_url # PERSISTENCE
            untappd_payload['untappd_url'] = untappd_url # PK
            
            logger.info(f"  ✅ Found URL: {untappd_url}")
            
            # Check if this URL already exists in untappd_data table
            existing_entry = supabase.table('untappd_data').select('untappd_url, fetched_at').eq('untappd_url', untappd_url).execute()
            
            if existing_entry.data:
                logger.info(f"  💾 Data already exists in untappd_data. Linking only.")
                untappd_payload = {} 
            else:
                if offline:
                     logger.info(f"  ⏭️  [Offline] URL found but details missing. Skipping scrape.")
                     untappd_payload = {} 
                else:
                    # New URL, definitely scrape
                    if "untappd.com/b/" in untappd_url:
                        await asyncio.sleep(2)  # Rate limiting
                        logger.info(f"  🔄 Scraping beer details...")
                        details = scrape_beer_details(untappd_url)
                        if details:
                            mapped = map_details_to_payload(details)
                            untappd_payload.update(mapped)
                            untappd_payload['untappd_url'] = untappd_url # Ensure PK is set
                            logger.info(f"  ✅ Details scraped: {details.get('untappd_style', 'N/A')}")
                        else:
                            logger.warning(f"  ⚠️  Could not scrape details from page")
                            untappd_payload['fetched_at'] = datetime.now(timezone.utc).isoformat()
    
    except Exception as e:
        logger.error(f"  ❌ Untappd search error: {e}")
        return None
    
    # Commit updates
    return await commit_updates(beer, untappd_payload, gemini_updates, scraped_updates)


async def process_beer_refresh(beer: dict):
    """
    Process a beer in 'refresh' mode:
    1. We have the URL.
    2. Direct scrape to update details.
    """
    untappd_url = beer.get('untappd_url')
    if not untappd_url or "untappd.com/b/" not in untappd_url:
        logger.warning(f"  ⚠️  Invalid Untappd URL: {untappd_url}")
        return None
        
    logger.info(f"  🔄 Refreshing: {beer.get('beer_name', 'Unknown')} ({untappd_url})")
    
    untappd_payload = {}
    try:
        await asyncio.sleep(2)  # Rate limiting
        details = scrape_beer_details(untappd_url)
        if details:
            untappd_payload = map_details_to_payload(details)
            untappd_payload['untappd_url'] = untappd_url # Ensure PK is present
            logger.info(f"  ✅ Details updated: Rating {details.get('untappd_rating', 'N/A')}")
        else:
            logger.warning(f"  ⚠️  Could not scrape details")
            untappd_payload = {
                'untappd_url': untappd_url,
                'fetched_at': datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"  ❌ Refresh error: {e}")
        return None

    # Commit only untappd_data updates
    return await commit_updates(beer, untappd_payload, {}, {})


async def commit_updates(beer, untappd_payload, gemini_updates, scraped_updates):
    supabase = get_supabase_client()
    success = False
    
    # 1. Upsert to untappd_data
    if untappd_payload:
        try:
            supabase.table('untappd_data').upsert(untappd_payload).execute()
            logger.info(f"  💾 Saved to untappd_data")
            success = True
        except Exception as e:
            logger.error(f"  ❌ Error saving to untappd_data: {e}")

    # 2. Update gemini_data (PERSISTENCE)
    if gemini_updates and beer.get('url'):
        try:
            supabase.table('gemini_data').update(gemini_updates).eq('url', beer['url']).execute()
            logger.info(f"  💾 Persisted URL to gemini_data")
        except Exception as e:
            logger.error(f"  ⚠️ Error updating gemini_data: {e}")

    # 3. Update scraped_beers (Link)
    if scraped_updates and beer.get('url'):
        try:
            supabase.table('scraped_beers').update(scraped_updates).eq('url', beer['url']).execute()
            logger.info(f"  🔗 Linked scraping_beers")
            success = True
        except Exception as e:
            logger.error(f"  ❌ Error updating scraped_beers: {e}")
            
    return untappd_payload or scraped_updates


async def enrich_untappd(limit: int = 50, mode: str = 'missing', shop_filter: str = None, name_filter: str = None) -> List[str]:
    """
    Enrich beers with Untappd data.
    mode: 'missing' (default) or 'refresh'
    shop_filter: Optional shop name to filter by
    name_filter: Optional beer name substring to filter by
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
    
    total_processed = 0
    total_success = 0
    
    batch_size = 1000 if limit > 1000 else limit
    
    collected_brewery_urls = set()
    
    while True:
        beers = []
        
        if mode == 'missing':
            logger.info(f"\n📂 Loading batch of MISSING beers (Limit: {batch_size})...")
            query = supabase.table('beer_info_view') \
                .select('*') \
                .is_('untappd_url', None) \
                .or_('is_set.is.null,is_set.eq.false')
            
            if shop_filter:
                query = query.eq('shop', shop_filter)

            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')
                
            response = query.order('first_seen', desc=True) \
                .limit(batch_size) \
                .execute()
            beers = response.data
            
        elif mode == 'refresh':
            logger.info(f"\n📂 Loading batch of REFRESH beers (Limit: {batch_size})...")
            
            # Calculate cutoff date (5 days ago)
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            
            query = supabase.table('beer_info_view') \
                .select('url, name, untappd_url, stock_status, untappd_fetched_at') \
                .not_.is_('untappd_url', None) \
                .neq('stock_status', 'Sold Out') \
                .or_(f'untappd_fetched_at.is.null,untappd_fetched_at.lt.{cutoff_date}')  # Only items not updated in 5+ days

            if shop_filter:
                query = query.eq('shop', shop_filter)

            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')

            response = query.order('untappd_fetched_at', desc=False, nullsfirst=True) \
                .limit(batch_size) \
                .execute()
            beers = response.data
            
        logger.info(f"  Found {len(beers)} beers to process")
        
        if not beers:
            logger.info("\n✨ No more beers to process!")
            break
        
        processed_urls = set() # Track unique URLs in this batch to avoid redundant refreshes
        
        # Process beers
        for i, beer in enumerate(beers, 1):

            # Track by product URL to avoid duplicates in batch, not Untappd URL (which might be None)
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
                result = await process_beer_missing(beer)
            elif mode == 'refresh':
                result = await process_beer_refresh(beer)
            
            if result:
                total_success += 1
                if isinstance(result, dict):
                    b_url = result.get('untappd_brewery_url')
                    if b_url:
                        collected_brewery_urls.add(b_url)
                
            await asyncio.sleep(1)  # Rate limiting between searches
        
        total_processed += len(beers)
        
        if total_processed >= limit:
            break

    # Final stats
    logger.info(f"\n{'='*70}")
    logger.info("✨ Untappd enrichment completed!")
    logger.info(f"{'='*70}")
    
    return list(collected_brewery_urls)

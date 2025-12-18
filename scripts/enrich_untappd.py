#!/usr/bin/env python3
"""
Untappd-only enrichment script for Supabase
Enriches beers with Untappd data.
Modes:
- missing: Finds Untappd URLs for beers that don't have one.
- refresh: Updates details (rating, ABV, etc.) for beers that already have a URL.
"""
import asyncio
import os
import sys
import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import get_untappd_url, scrape_beer_details, scrape_brewery_details, UntappdBeerDetails
# from app.services.brewery_manager import BreweryManager

# Configure Logging
from scripts.utils.script_utils import setup_script

# Setup Supabase and Logging
supabase, logger = setup_script("enrich_untappd")


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


async def process_beer_missing(beer, supabase, offline=False):
    """
    Process a beer in 'missing' mode:
    1. Check if URL exists in untappd_data already.
    2. Search Untappd (Web or Local DB).
    3. If found, save URL and scrape details.
    """
    scraped_updates = {} # Updates for scraped_beers table (link)
    untappd_payload = {} # Updates for untappd_data table (master info)
    gemini_updates = {}  # Updates for gemini_data table (persistence)
    
    # Extract brewery and beer names
    brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')

    # Check for 'is_set' flag from Gemini
    # Note: 'beer' object comes from beer_info_view, which joins gemini_data
    # We need to make sure 'is_set' is available in the view or fetch it.
    # The view definition in supabase_schema.sql needs to be updated to include 'is_set' IF we want it here.
    # However, enrich_gemini passes the updated 'beer' dict if chained.
    # But for standalone runs, we need checking.
    
    # If the view doesn't have it yet (we didn't update the view definition in this task, just the table),
    # we might miss it in standalone 'enrich_untappd' runs. 
    # BUT, 'enrich_gemini' passes the payload directly.
    # For safety, let's check it. If it's missing in dict, we assume False.
    
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
                    untappd_url = persistence.data['untappd_url']
                    logger.info(f"  ✅ [Persistence] Found link in gemini_data: {untappd_url}")
            except Exception as e:
                logger.error(f"  ⚠️ Error checking persistence: {e}")

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
                untappd_url = get_untappd_url(brewery, beer_name, beer_name_jp=beer_name_jp_clean)
        
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
                            
                            # --- Brewery Enrichment Integration ---
                            # Handled by enrich_breweries.py via collected URLs return value
                            b_url = details.get('untappd_brewery_url')
                            # -------------------------------------
                        else:
                            logger.warning(f"  ⚠️  Could not scrape details from page")
                            untappd_payload['fetched_at'] = datetime.now(timezone.utc).isoformat()
    
    except Exception as e:
        logger.error(f"  ❌ Untappd search error: {e}")
        return None
    
    # Commit updates
    return await commit_updates(beer, supabase, untappd_payload, gemini_updates, scraped_updates)



async def process_beer_refresh(beer, supabase):
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
    return await commit_updates(beer, supabase, untappd_payload, {}, {})


async def commit_updates(beer, supabase, untappd_payload, gemini_updates, scraped_updates):
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
            logger.info(f"  🔗 Linked scraped_beer")
            success = True
        except Exception as e:
            logger.error(f"  ❌ Error updating scraped_beers: {e}")
            
    return untappd_payload or scraped_updates


async def enrich_untappd(limit: int = 50, mode: str = 'missing', shop_filter: str = None, name_filter: str = None):
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
    
    # Create Supabase client
    # supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) # Global 'supabase' used

    
    total_processed = 0
    total_success = 0
    
    batch_size = 1000 if limit > 1000 else limit
    
    collected_brewery_urls = set()
    
    while True:
        beers = []
        
        # ... (query logic remains same, implicit via context of file) ...
        # I need to match the indentation and context.
        # It's safer to just insert the init before the loop and the add inside the loop.
        
        # We need to rely on 'process_beer_*' returning something useful or we extract it.
        # process_beer_missing returns the payload which contains 'untappd_brewery_url'
        
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
            query = supabase.table('beer_info_view') \
                .select('name, untappd_url, stock_status, untappd_fetched_at') \
                .not_.is_('untappd_url', None)

            if shop_filter:
                query = query.eq('shop', shop_filter)

            if name_filter:
                query = query.ilike('name', f'%{name_filter}%')

            response = query.order('untappd_fetched_at', desc=False) \
                .limit(batch_size) \
                .execute()
            beers = response.data
            
        logger.info(f"  Found {len(beers)} beers to process")
        
        if not beers:
            logger.info("\n✨ No more beers to process!")
            break
        
        processed_urls = set() # Track unique URLs in this batch to avoid redundant refreshes
        consecutive_sold_out = 0
        
        # Process beers
        for i, beer in enumerate(beers, 1):
            if beer.get('stock_status') == 'Sold Out':
                 consecutive_sold_out += 1
            else:
                 consecutive_sold_out = 0
                 
            if consecutive_sold_out >= 30 and not name_filter:
                logger.info(f"\n🛑 Stopping refresh: {consecutive_sold_out} consecutive sold-out items detected.")
                logging.info(f"  (Processing stopped to conserve resources on old/sold-out items)")
                return

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
                result = await process_beer_missing(beer, supabase)
            elif mode == 'refresh':
                result = await process_beer_refresh(beer, supabase)
            
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
    
    # Collect all brewery URLs from this run
    # Since we are not tracking them explicitly in a set across batches (only processed_urls tracks products),
    # we should ideally track them.
    # But for now, let's just return an empty set or modify the loop to track them.
    # WAIT: We need to modify the loop to track them.
    
    return list(collected_brewery_urls)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Untappd in Supabase')
    parser.add_argument('--limit', type=int, default=1000, help='Batch size (default 1000)')
    parser.add_argument('--mode', choices=['missing', 'refresh'], default='missing', help="Enrichment mode")
    parser.add_argument('--shop_filter', type=str, default=None, help="Process only specific shop")
    parser.add_argument('--name_filter', type=str, default=None, help="Process only beers matching name")
    
    args = parser.parse_args()
    
    asyncio.run(enrich_untappd(limit=args.limit, mode=args.mode, shop_filter=args.shop_filter, name_filter=args.name_filter))

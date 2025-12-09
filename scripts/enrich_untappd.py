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
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import get_untappd_url, scrape_beer_details
from app.services.brewery_manager import BreweryManager

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

# Get credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)


def map_details_to_payload(details):
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
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }


async def process_beer_missing(beer, supabase):
    """
    Process a beer in 'missing' mode:
    1. Check if URL exists in untappd_data already (by brewery/beer name search potentially, but here we invoke search).
    2. Search Untappd.
    3. If found, save URL and scrape details.
    """
    scraped_updates = {} # Updates for scraped_beers table (link)
    untappd_payload = {} # Updates for untappd_data table (master info)
    gemini_updates = {}  # Updates for gemini_data table (persistence)
    
    # Extract brewery and beer names
    brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
    
    if not brewery or not beer_name:
        print(f"  ⚠️  Missing brewery or beer name - skipping")
        return None
    
    try:
        untappd_url = beer.get('untappd_url')
        
        # Search if no URL
        if not untappd_url:
            print(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
            untappd_url = get_untappd_url(brewery, beer_name)
        
        if untappd_url:
            scraped_updates['untappd_url'] = untappd_url
            gemini_updates['untappd_url'] = untappd_url # PERSISTENCE
            untappd_payload['untappd_url'] = untappd_url # PK
            
            print(f"  ✅ Found URL: {untappd_url}")
            
            # Check if this URL already exists in untappd_data table
            existing_entry = supabase.table('untappd_data').select('untappd_url, fetched_at').eq('untappd_url', untappd_url).execute()
            
            if existing_entry.data:
                print(f"  💾 Data already exists in untappd_data. Linking only.")
                 # We still proceed to update links (scraped_beers, gemini_data)
                 # We do NOT update untappd_data payload to avoid overwriting with stale/empty data unless we scrape.
                 # Actually, if we found it, we might want to check if it needs refresh? 
                 # But 'missing' mode focuses on finding the link.
                untappd_payload = {} 
            else:
                # New URL, definitely scrape
                if "untappd.com/b/" in untappd_url:
                    await asyncio.sleep(2)  # Rate limiting
                    print(f"  🔄 Scraping beer details...")
                    details = scrape_beer_details(untappd_url)
                    if details:
                        mapped = map_details_to_payload(details)
                        untappd_payload.update(mapped)
                        untappd_payload['untappd_url'] = untappd_url # Ensure PK is set
                        print(f"  ✅ Details scraped: {details.get('untappd_style', 'N/A')}")
                    else:
                        print(f"  ⚠️  Could not scrape details from page")
                        untappd_payload['fetched_at'] = datetime.now(timezone.utc).isoformat()
    
    except Exception as e:
        print(f"  ❌ Untappd search error: {e}")
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
        print(f"  ⚠️  Invalid Untappd URL: {untappd_url}")
        return None
        
    print(f"  🔄 Refreshing: {beer.get('beer_name', 'Unknown')} ({untappd_url})")
    
    untappd_payload = {}
    try:
        await asyncio.sleep(2)  # Rate limiting
        details = scrape_beer_details(untappd_url)
        if details:
            untappd_payload = map_details_to_payload(details)
            untappd_payload['untappd_url'] = untappd_url # Ensure PK is present
            print(f"  ✅ Details updated: Rating {details.get('untappd_rating', 'N/A')}")
        else:
            print(f"  ⚠️  Could not scrape details")
            # Update fetched_at anyway to avoid stuck retry loops?
            untappd_payload = {
                'untappd_url': untappd_url,
                'fetched_at': datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        print(f"  ❌ Refresh error: {e}")
        return None

    # Commit only untappd_data updates
    return await commit_updates(beer, supabase, untappd_payload, {}, {})


async def commit_updates(beer, supabase, untappd_payload, gemini_updates, scraped_updates):
    success = False
    
    # 1. Upsert to untappd_data
    if untappd_payload:
        try:
            supabase.table('untappd_data').upsert(untappd_payload).execute()
            print(f"  💾 Saved to untappd_data")
            success = True
        except Exception as e:
            print(f"  ❌ Error saving to untappd_data: {e}")

    # 2. Update gemini_data (PERSISTENCE)
    if gemini_updates and beer.get('url'):
        try:
            supabase.table('gemini_data').update(gemini_updates).eq('url', beer['url']).execute()
            print(f"  💾 Persisted URL to gemini_data")
        except Exception as e:
            print(f"  ⚠️ Error updating gemini_data: {e}")

    # 3. Update scraped_beers (Link)
    if scraped_updates and beer.get('url'):
        try:
            supabase.table('scraped_beers').update(scraped_updates).eq('url', beer['url']).execute()
            print(f"  🔗 Linked scraped_beer")
            success = True
        except Exception as e:
             # If we fail here, it's likely because there is no scraped_beers entry (e.g. in refresh mode if we passed a dict without url)
             # But in refresh mode scraped_updates is empty usually.
            print(f"  ❌ Error updating scraped_beers: {e}")
            
    return untappd_payload or scraped_updates


async def enrich_untappd(limit: int = 50, mode: str = 'missing'):
    """
    Enrich beers with Untappd data.
    mode: 'missing' (default) or 'refresh'
    """
    print("=" * 70)
    print(f"🍺 Untappd Enrichment (Mode: {mode.upper()})")
    print("=" * 70)
    print(f"Batch size: {limit}")
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    total_processed = 0
    total_success = 0
    
    batch_size = 1000 if limit > 1000 else limit
    
    while True:
        beers = []
        
        if mode == 'missing':
            # Get beers that have Gemini data but no Untappd URL (or no Rating)
            # Using beer_info_view
            print(f"\n📂 Loading batch of MISSING beers (Limit: {batch_size})...")
            response = supabase.table('beer_info_view') \
                .select('*') \
                .not_.is_('brewery_name_en', None) \
                .is_('untappd_url', None) \
                .order('first_seen', desc=True) \
                .limit(batch_size) \
                .execute()
            beers = response.data
            
        elif mode == 'refresh':
            # Get beers that HAVE Untappd URL, ordered by untappd_fetched_at ASC (oldest first)
            # We use beer_info_view to get stock_status for "stop if consecutive sold out" logic.
            print(f"\n📂 Loading batch of REFRESH beers (Limit: {batch_size})...")
            response = supabase.table('beer_info_view') \
                .select('name, untappd_url, stock_status, untappd_fetched_at') \
                .not_.is_('untappd_url', None) \
                .order('untappd_fetched_at', desc=False) \
                .limit(batch_size) \
                .execute()
            beers = response.data
            
        print(f"  Found {len(beers)} beers to process")
        
        if not beers:
            print("\n✨ No more beers to process!")
            break
        
        processed_urls = set() # Track unique URLs in this batch to avoid redundant refreshes
        consecutive_sold_out = 0
        
        # Process beers
        for i, beer in enumerate(beers, 1):
            # Check stock status for early stop logic
            # "Sold Out" is the standard string from our scrapers
            if beer.get('stock_status') == 'Sold Out':
                 consecutive_sold_out += 1
            else:
                 consecutive_sold_out = 0
                 
            if consecutive_sold_out >= 30:
                print(f"\n🛑 Stopping refresh: {consecutive_sold_out} consecutive sold-out items detected.")
                # We want to exit the entire script/process
                print(f"  (Processing stopped to conserve resources on old/sold-out items)")
                return

            untappd_url = beer.get('untappd_url')
            
            # Skip if we already processed this URL in this batch (e.g. multiple vintages pointing to same Untappd entry)
            if untappd_url in processed_urls:
                continue
            processed_urls.add(untappd_url)

            name_display = beer.get('name', beer.get('beer_name', 'Unknown'))
            print(f"\n{'='*70}")
            print(f"[Batch {i}/{len(beers)} | Total {total_processed + i}] Processing: {name_display[:60]}")
            print(f"{'='*70}")
            
            result = None
            if mode == 'missing':
                result = await process_beer_missing(beer, supabase)
            elif mode == 'refresh':
                result = await process_beer_refresh(beer, supabase)
            
            if result:
                total_success += 1
                
            await asyncio.sleep(1)  # Rate limiting between searches
            
        total_processed += len(beers)
        
        # In refresh mode with duplicates in view, we might process fewer than 'limit' unique items.
        # But checking total_processed against limit is safely approximate.
        if total_processed >= limit:
            break

    # Final stats
    print(f"\n{'='*70}")
    print("📈 Final Statistics")
    print(f"{'='*70}")
    print(f"  Total processed: {total_processed}")
    print(f"  Success: {total_success}")
    print(f"  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{'='*70}")
    print("✨ Untappd enrichment completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Untappd in Supabase')
    parser.add_argument('--limit', type=int, default=1000, help='Batch size (default 1000)')
    parser.add_argument('--mode', choices=['missing', 'refresh'], default='missing', help="Enrichment mode")
    
    args = parser.parse_args()
    
    asyncio.run(enrich_untappd(limit=args.limit, mode=args.mode))

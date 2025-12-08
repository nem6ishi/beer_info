#!/usr/bin/env python3
"""
Cloud scraper that writes directly to Supabase.
This script orchestrates the scraping process for multiple beer sites (Beervolta, Chouseiya, Ichigo Ichie).
It gathers data, calculates display timestamps for sorting, and upserts the data into Supabase.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers import beervolta, chouseiya, ichigo_ichie

# Get Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)


def parse_timestamp(ts_str):
    """
    Convert timestamp string to ISO format.
    
    Args:
        ts_str (str): Timestamp string in 'Y/m/d H:M:S' format.
        
    Returns:
        str: ISO formatted timestamp string or None if parsing fails.
    """
    if not ts_str:
        return None
    try:
        dt = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
        return dt.isoformat()
    except:
        return None


async def scrape_to_supabase(limit: int = None, reverse: bool = False):
    """
    Scrape and write directly to Supabase.
    
    Args:
        limit (int, optional): Limit the number of items to scrape per store. Defaults to None.
        reverse (bool, optional): Scrape in reverse order (Last Page -> First Page). Defaults to False.
    """
    print("=" * 60)
    print("🍺 Cloud Scraper (writing to Supabase)")
    if reverse:
        print("🔄 Reverse Order: SCRAPING FROM LAST PAGE TO FIRST")
        print("ℹ️  Sold-out threshold stops are DISABLED in reverse mode")
    print("=" * 60)
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get existing beers from Supabase to check for updates vs new items
    print("\n📂 Loading existing beers from Supabase...")
    existing_response = supabase.table('beers').select('url, first_seen, brewery_name_en, brewery_name_jp, untappd_url, untappd_fetched_at, stock_status').execute()
    existing_data = {beer['url']: beer for beer in existing_response.data}
    print(f"  Loaded {len(existing_data)} existing beers")
    
    # Fetch existing metadata to use as hints
    scraper_names = ['beervolta', 'chouseiya', 'ichigo_ichie']
    display_names = ['BeerVolta', 'Chouseiya', 'Ichigo Ichie']
    
    stored_metadata = {}
    try:
        meta_response = supabase.table('scraper_metadata').select('*').execute()
        stored_metadata = {row['store_name']: row['last_page'] for row in meta_response.data}
        print("ℹ️  Loaded scraper metadata hints.")
    except Exception as e:
        print(f"⚠️  Could not load scraper_metadata (Table might not exist yet): {e}")

    # Run scrapers in parallel
    print("\n🔍 Running scrapers in parallel...")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit, reverse=reverse, start_page_hint=stored_metadata.get('beervolta')),
        chouseiya.scrape_chouseiya(limit=limit, reverse=reverse, start_page_hint=stored_metadata.get('chouseiya')),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit, reverse=reverse, start_page_hint=stored_metadata.get('ichigo_ichie')),
        return_exceptions=True
    )
    
    # Process each scraper result separately to maintain per-store order
    scraper_results = []
    scraper_metadata_updates = {} # Store updates: {store_name: max_page}

    for i, res in enumerate(results):
        store_key = scraper_names[i]
        display_name = display_names[i]
        
        items = []
        max_page = None
        
        if isinstance(res, tuple):
            items = res[0]
            max_page = res[1]
        elif isinstance(res, list):
            # Backward compatibility or if I missed updating one scraper
            items = res
        elif isinstance(res, Exception):
            print(f"  ❌ {display_name}: Error - {res}")
            scraper_results.append([])
            continue
            
        print(f"  ✅ {display_name}: {len(items)} items")
        scraper_results.append(items)
        
        if max_page is not None:
            prev_max = stored_metadata.get(store_key)
            if prev_max is not None:
                if max_page != prev_max:
                    print(f"  🔄 {display_name}: Last page changed from {prev_max} to {max_page}")
                else:
                    print(f"  ℹ️  {display_name}: Last page unchanged ({max_page})")
            else:
                print(f"  🆕 {display_name}: Computed last page: {max_page}")
            
            scraper_metadata_updates[store_key] = max_page

    # Update metadata in DB
    if scraper_metadata_updates:
        print("\n📝 Updating scraper metadata...")
        for store_name, last_page in scraper_metadata_updates.items():
            try:
                data = {
                    'store_name': store_name,
                    'last_page': last_page,
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                supabase.table('scraper_metadata').upsert(data).execute()
                print(f"  Saved metadata for {store_name}: query_last_page={last_page}")
            except Exception as e:
                print(f"  ⚠️  Failed to update metadata for {store_name}: {e}")

    # Flatten all results for total count
    new_scraped_items = []
    for res in scraper_results:
        new_scraped_items.extend(res)
    
    print(f"\n📊 Total scraped: {len(new_scraped_items)} items")
    
    # Process and upsert
    current_time = datetime.now(timezone.utc)
    current_time_str = current_time.strftime('%Y/%m/%d %H:%M:%S')
    current_time_iso = current_time.isoformat()
    
    new_count = 0
    updated_count = 0
    
    # Calculate global totals
    total_items = len(new_scraped_items)
    
    beers_to_upsert = []
    
    # Assign display_timestamp PER STORE to maintain each store's display order
    # Process each store's results separately
    global_index = 0
    for store_items in scraper_results:
        if not store_items:
            continue
            
        for new_item in store_items:
            url = new_item.get('url')
            if not url:
                continue
            
            existing = existing_data.get(url)
            is_restock = False
            
            if existing:
                prev_stock = (existing.get('stock_status') or '').lower()
                new_stock = (new_item.get('stock_status') or '').lower()
                
                was_sold_out = 'sold' in prev_stock or 'out' in prev_stock
                is_now_available = not ('sold' in new_stock or 'out' in new_stock)
                
                if was_sold_out and is_now_available:
                    is_restock = True
                    print(f"  🔄 Restock: {new_item.get('name', 'Unknown')[:50]}")

            beer_data = {
                'url': url,
                'name': new_item.get('name'),
                'price': new_item.get('price'),
                'image': new_item.get('image'),
                'stock_status': new_item.get('stock_status'),
                'shop': new_item.get('shop'),
                'last_seen': current_time_iso,
            }
            
            if existing:
                # Update existing beer
                # Preserve existing enrichment data
                beer_data['first_seen'] = existing.get('first_seen')
                beer_data['brewery_name_en'] = existing.get('brewery_name_en')
                beer_data['brewery_name_jp'] = existing.get('brewery_name_jp')
                beer_data['untappd_url'] = existing.get('untappd_url')
                beer_data['untappd_fetched_at'] = existing.get('untappd_fetched_at')
                # available_since used to track restocks, but user said first_seen is enough.
                # keeping it simple, not modifying created_at/first_seen
                
                updated_count += 1
            else:
                # New beer
                beer_data['first_seen'] = current_time_iso
                new_count += 1
            
            beers_to_upsert.append(beer_data)
    
    # Batch upsert to Supabase
    if beers_to_upsert:
        batch_size = 1000
        for i in range(0, len(beers_to_upsert), batch_size):
            batch = beers_to_upsert[i:i + batch_size]
            print(f"\n💾 Upserting batch {i // batch_size + 1} ({len(batch)} beers)...")
            try:
                supabase.table('beers').upsert(batch, on_conflict='url').execute()
                print(f"  ✅ Upserted {len(batch)} beers")
            except Exception as e:
                print(f"  ❌ Error upserting batch: {e}")
    
    print(f"\n{'='*60}")
    print("📈 Statistics:")
    print(f"  🆕 New beers: {new_count}")
    print(f"  🔄 Updated beers: {updated_count}")
    print(f"  📦 Total upserted: {len(beers_to_upsert)}")
    print("=" * 60)
    print("✨ Scraping completed!")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape beer data to Supabase')
    parser.add_argument('--limit', type=int, help='Limit items per scraper')
    parser.add_argument('--reverse', action='store_true', help='Scrape in reverse order')
    
    args = parser.parse_args()
    
    asyncio.run(scrape_to_supabase(limit=args.limit, reverse=args.reverse))

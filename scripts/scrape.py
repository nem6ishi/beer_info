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


async def scrape_to_supabase(limit: int = None, smart: bool = False, full_scrape: bool = False):
    """
    Scrape and write directly to Supabase (scraped_beers table).
    
    Args:
        limit (int, optional): Limit the number of items to scrape per store. Defaults to None.
        smart (bool, optional): Smart scrape: Detect new items and scrape in reverse order. Defaults to False.
        full_scrape (bool, optional): If True, ignore sold-out threshold/early stopping. Defaults to False.
    """
    print("=" * 60)
    print("🍺 Cloud Scraper (writing to Supabase: scraped_beers)")
    if smart:
        print("🧠 Smart Mode ENABLED: Scanning for new items first.")
    if full_scrape:
        print("🔥 Full Scrape Mode ENABLED: Ignoring sold-out threshold/early stopping.")
    print("=" * 60)
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get existing beers from Supabase to check for updates vs new items
    print("\n📂 Loading existing beers from scraped_beers...")
    # Select only what we need to preserve or check
    existing_response = supabase.table('scraped_beers').select('url, first_seen, stock_status, untappd_url').execute()
    existing_data = {beer['url']: beer for beer in existing_response.data}
    existing_urls = set(existing_data.keys())
    print(f"  Loaded {len(existing_data)} existing beers")
    
    scraper_names = ['beervolta', 'chouseiya', 'ichigo_ichie']
    display_names = ['BeerVolta', 'Chouseiya', 'Ichigo Ichie']

    # Run scrapers in parallel
    print("\n🔍 Running scrapers in parallel...")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit, existing_urls=existing_urls if smart else None, full_scrape=full_scrape),
        chouseiya.scrape_chouseiya(limit=limit, existing_urls=existing_urls if smart else None, full_scrape=full_scrape),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit, existing_urls=existing_urls if smart else None, full_scrape=full_scrape),
        return_exceptions=True
    )
    
    # Process each scraper result separately to maintain per-store order
    scraper_results = []
    
    for i, res in enumerate(results):
        display_name = display_names[i]
        
        items = []
        
        if isinstance(res, list):
            items = res
        elif isinstance(res, Exception):
            print(f"  ❌ {display_name}: Error - {res}")
            scraper_results.append([])
            continue
            
        print(f"  ✅ {display_name}: {len(items)} items")
        scraper_results.append(items)

    # Flatten all results for total count
    new_scraped_items = []
    for res in scraper_results:
        new_scraped_items.extend(res)
    
    print(f"\n📊 Total scraped: {len(new_scraped_items)} items")
    
    # Process and upsert
    current_time = datetime.now(timezone.utc)
    current_time_iso = current_time.isoformat()
    
    new_count = 0
    updated_count = 0
    
    beers_to_upsert = []
    
    global_index = 0
    base_time = datetime.now(timezone.utc)
    
    for store_items in scraper_results:
        if not store_items:
            continue
            
        # Items are likely Newest -> Oldest (Page 1 top -> Page N bottom)
        # We want to process Oldest -> Newest.
        # Smart Mode buffer returns Newest -> Oldest (Page 1 -> N).
        # So we almost ALWAYS want to reverse the list to assign timestamps Oldest -> Newest.
        items_to_process = list(reversed(store_items))

        for new_item in items_to_process:
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

            # Assign increasing timestamp with minimal difference (microseconds)
            # This ensures order is preserved without significant clock drift
            item_time = base_time + timedelta(milliseconds=global_index)
            item_time_iso = item_time.isoformat()
            global_index += 1

            beer_data = {
                'url': url,
                'name': new_item.get('name'),
                'price': new_item.get('price'),
                'image': new_item.get('image'),
                'stock_status': new_item.get('stock_status'),
                'shop': new_item.get('shop'),
                'last_seen': current_time_iso, # Last seen is always "Now"
            }
            
            if existing:
                # Update existing beer
                beer_data['first_seen'] = existing.get('first_seen')
                # Preserve link to Untappd Data
                if existing.get('untappd_url'):
                    beer_data['untappd_url'] = existing.get('untappd_url')
                
                updated_count += 1
            else:
                # New beer
                beer_data['first_seen'] = item_time_iso
                new_count += 1
            
            beers_to_upsert.append(beer_data)
    
    # Batch upsert to Supabase
    if beers_to_upsert:
        batch_size = 1000
        for i in range(0, len(beers_to_upsert), batch_size):
            batch = beers_to_upsert[i:i + batch_size]
            print(f"\n💾 Upserting batch {i // batch_size + 1} ({len(batch)} beers)...")
            try:
                # Upsert to scraped_beers
                supabase.table('scraped_beers').upsert(batch, on_conflict='url').execute()
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
    parser.add_argument('--smart', action='store_true', help='Smart scrape')
    parser.add_argument('--full', action='store_true', help='Full scrape (ignore sold-out threshold)')
    
    args = parser.parse_args()
    
    asyncio.run(scrape_to_supabase(limit=args.limit, smart=args.smart, full_scrape=args.full))

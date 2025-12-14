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


    except:
        return None

def parse_price(price_str):
    """
    Extract numeric value from price string.
    
    Args:
        price_str (str): Price string (e.g., "¥1,000", "1500円")
        
    Returns:
        int/float: Numeric price or None
    """
    if not price_str:
        return None
    try:
        # Remove non-digits
        import re
        clean = re.sub(r'[^0-9]', '', str(price_str))
        if clean:
            return int(clean)
        return None
    except:
        return None

async def scrape_to_supabase(limit: int = None, new_only: bool = False, full_scrape: bool = False, reset_first_seen: bool = False):
    """
    Scrape and write directly to Supabase (scraped_beers table).
    
    Args:
        limit (int, optional): Limit the number of items to scrape per store. Defaults to None.
        new_only (bool, optional): New items only: Detect new items and scrape in reverse order. Defaults to False.
        full_scrape (bool, optional): If True, ignore sold-out threshold/early stopping. Defaults to False.
    """
    print("=" * 60)
    print("🍺 Cloud Scraper (writing to Supabase: scraped_beers)")
    if new_only:
        print("🍺 新商品スクレイプ (New Product Scrape) ENABLED: 既存商品が30件続いたら停止")
    if full_scrape:
        print("🔥 全件スクレイプ (Full Scrape) ENABLED: 停止リミットを無視して全件取得")
    print("=" * 60)
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get existing beers from Supabase to check for updates vs new items
    # Get existing beers from Supabase to check for updates vs new items
    print("\n📂 Loading existing beers from scraped_beers...")
    
    all_existing_beers = []
    chunk_size = 1000
    start = 0
    
    while True:
        # Fetch in chunks
        response = supabase.table('scraped_beers').select('url, first_seen, stock_status, untappd_url').range(start, start + chunk_size - 1).execute()
        
        if not response.data:
            break
            
        all_existing_beers.extend(response.data)
        
        if len(response.data) < chunk_size:
            break
            
        start += chunk_size
        print(f"  Loaded {len(all_existing_beers)} items...", end='\r')

    existing_data = {beer['url']: beer for beer in all_existing_beers}
    existing_urls = set(existing_data.keys())
    print(f"  Loaded {len(existing_data)} existing beers (Complete)")
    
    scraper_names = ['beervolta', 'chouseiya', 'ichigo_ichie']
    display_names = ['BeerVolta', 'Chouseiya', 'Ichigo Ichie']

    # Run scrapers in parallel
    print("\n🔍 Running scrapers in parallel...")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
        chouseiya.scrape_chouseiya(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
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
            # This ensures order is preserved while keeping timestamps almost identical
            item_time = base_time + timedelta(microseconds=global_index)
            item_time_iso = item_time.isoformat()
            global_index += 1

            beer_data = {
                'url': url,
                'name': new_item.get('name'),
                'price': new_item.get('price'),
                'price_value': parse_price(new_item.get('price')),
                'image': new_item.get('image'),
                'stock_status': new_item.get('stock_status'),
                'shop': new_item.get('shop'),
                'last_seen': current_time_iso, # Last seen is always "Now"
            }
            
            if existing and not reset_first_seen:
                # In New Product Scrape mode, skip updating existing items unless it's a restock
                if new_only and not is_restock:
                    continue

                # Update existing beer
                if is_restock:
                    # Treat as new for sorting purposes
                    beer_data['first_seen'] = item_time_iso
                else:
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
    parser.add_argument('--new', action='store_true', help='New items only scrape')
    parser.add_argument('--full', action='store_true', help='Full scrape (ignore sold-out threshold)')
    parser.add_argument('--reset-dates', action='store_true', help='Reset first_seen timestamps')
    
    args = parser.parse_args()
    
    asyncio.run(scrape_to_supabase(limit=args.limit, new_only=args.new, full_scrape=args.full, reset_first_seen=args.reset_dates))

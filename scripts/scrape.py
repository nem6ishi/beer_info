#!/usr/bin/env python3
"""
Cloud scraper that writes directly to Supabase
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from supabase import create_client, Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers import beervolta, chouseiya, ichigo_ichie

# Get Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)


def parse_timestamp(ts_str):
    """Convert timestamp string to ISO format"""
    if not ts_str:
        return None
    try:
        dt = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
        return dt.isoformat()
    except:
        return None


async def scrape_to_supabase(limit: int = None):
    """Scrape and write directly to Supabase"""
    print("=" * 60)
    print("🍺 Cloud Scraper (writing to Supabase)")
    print("=" * 60)
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get existing beers from Supabase
    print("\n📂 Loading existing beers from Supabase...")
    existing_response = supabase.table('beers').select('url, first_seen, brewery_name_en, brewery_name_jp, untappd_url, untappd_fetched_at, stock_status, available_since, restocked_at').execute()
    existing_data = {beer['url']: beer for beer in existing_response.data}
    print(f"  Loaded {len(existing_data)} existing beers")
    
    # Run scrapers
    print("\n🔍 Running scrapers in parallel...")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit),
        chouseiya.scrape_chouseiya(limit=limit),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit),
        return_exceptions=True
    )
    
    # Process each scraper result separately to maintain per-store order
    scraper_results = []
    for i, res in enumerate(results):
        scraper_names = ['BeerVolta', 'Chouseiya', 'Ichigo Ichie']
        if isinstance(res, list):
            print(f"  ✅ {scraper_names[i]}: {len(res)} items")
            scraper_results.append(res)
        elif isinstance(res, Exception):
            print(f"  ❌ {scraper_names[i]}: Error - {res}")
            scraper_results.append([])
    
    # Flatten all results for total count
    new_scraped_items = []
    for res in scraper_results:
        new_scraped_items.extend(res)
    
    print(f"\n📊 Total scraped: {len(new_scraped_items)} items")
    
    # Process and upsert
    current_time = datetime.now()
    current_time_str = current_time.strftime('%Y/%m/%d %H:%M:%S')
    current_time_iso = current_time.isoformat()
    
    new_count = 0
    updated_count = 0
    
    # Calculate global scrape_order (reverse-indexed across ALL shops)
    # First scraped item gets highest number, last gets 0
    total_items = len(new_scraped_items)
    
    beers_to_upsert = []
    
    # Assign display_timestamp PER STORE to maintain each store's display order
    # Process each store's results separately
    global_index = 0
    for store_items in scraper_results:
        if not store_items:
            continue
        
        # For each store, assign display_timestamp in order
        # First item in store gets newest timestamp for that store
        store_base_time = current_time - timedelta(seconds=global_index * 0.001)
        
        for store_index, new_item in enumerate(store_items):
            url = new_item.get('url')
            if not url:
                continue
            
            existing = existing_data.get(url)
            
            # Global reverse scrape_order: first item across all shops gets highest number
            reverse_order = total_items - global_index - 1
            
            # Calculate display_timestamp for this store
            # First item in store (store_index=0) gets NEWEST timestamp for this store
            # Last item in store gets OLDEST timestamp for this store
            # Result: ORDER BY display_timestamp DESC shows items in store order
            display_time_offset = store_index
            display_timestamp = store_base_time - timedelta(milliseconds=display_time_offset)
            
            beer_data = {
                'url': url,
                'name': new_item.get('name'),
                'price': new_item.get('price'),
                'image': new_item.get('image'),
                'stock_status': new_item.get('stock_status'),
                'shop': new_item.get('shop'),
                'scrape_order': reverse_order,  # Global reverse-indexed order (kept for compatibility)
                'scrape_timestamp': current_time_iso,  # Actual scrape time (same for all)
                'display_timestamp': display_timestamp.isoformat(),  # Per-store timestamp for display
                'last_seen': current_time_iso,
            }
            
            if existing:
                # Update existing beer
                beer_data['first_seen'] = existing.get('first_seen')
                beer_data['brewery_name_en'] = existing.get('brewery_name_en')
                beer_data['brewery_name_jp'] = existing.get('brewery_name_jp')
                beer_data['untappd_url'] = existing.get('untappd_url')
                beer_data['untappd_fetched_at'] = existing.get('untappd_fetched_at')
                
                # Restock detection
                prev_stock = (existing.get('stock_status') or '').lower()
                new_stock = (new_item.get('stock_status') or '').lower()
                
                was_sold_out = 'sold' in prev_stock or 'out' in prev_stock
                is_now_available = not ('sold' in new_stock or 'out' in new_stock)
                
                if was_sold_out and is_now_available:
                    beer_data['restocked_at'] = current_time_iso
                    beer_data['available_since'] = current_time_iso
                    print(f"  🔄 Restock: {new_item.get('name', 'Unknown')[:50]}")
                else:
                    beer_data['available_since'] = existing.get('available_since') or existing.get('first_seen')
                
                updated_count += 1
            else:
                # New beer
                beer_data['first_seen'] = current_time_iso
                beer_data['available_since'] = current_time_iso
                new_count += 1
            
            beers_to_upsert.append(beer_data)
            global_index += 1
    
    # Batch upsert
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
    
    args = parser.parse_args()
    
    asyncio.run(scrape_to_supabase(limit=args.limit))

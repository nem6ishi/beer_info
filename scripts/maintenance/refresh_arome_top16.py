
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

from app.scrapers.arome import scrape_arome

# Get Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials must be set")
    sys.exit(1)

def parse_price(price_str):
    if not price_str: return None
    try:
        import re
        clean = re.sub(r'[^0-9]', '', str(price_str))
        if clean: return int(clean)
        return None
    except: return None

async def refresh_arome_top16():
    print("=" * 60)
    print("🍺 Arôme Top 16 Refresh (Setting first_seen to NOW)")
    print("=" * 60)
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Get ALL existing Arôme URLs to skip redundant detail fetches
    print("  Loading existing Arôme URLs to optimize fetching...")
    existing_urls = set()
    start = 0
    chunk_size = 1000
    while True:
        existing_res = supabase.table('scraped_beers') \
            .select('url') \
            .eq('shop', 'Arôme') \
            .range(start, start + chunk_size - 1) \
            .execute()
        if not existing_res.data:
            break
        existing_urls.update(row['url'] for row in existing_res.data)
        if len(existing_res.data) < chunk_size:
            break
        start += chunk_size
    print(f"  Loaded {len(existing_urls)} existing URLs.")

    # 2. Scrape Top 16
    print("\n🔍 Scraping top 16 items from Arôme...")
    items = await scrape_arome(limit=16, existing_urls=existing_urls, full_scrape=True)
    
    if not items:
        print("❌ No items found.")
        return

    print(f"  Found {len(items)} items.")
    
    # 2. Get existing data to preserve fields
    urls = [item['url'] for item in items]
    existing_map = {}
    if urls:
        print("  Checking for existing data in DB...")
        res = supabase.table('scraped_beers').select('*').in_('url', urls).execute()
        for row in res.data:
            existing_map[row['url']] = row

    # 3. Prepare payload
    beers_to_upsert = []
    current_time = datetime.now(timezone.utc)
    base_time = current_time
    
    for i, item in enumerate(items):
        url = item.get('url')
        if not url: continue
        
        # Decrement time slightly for each subsequent item so Item 0 is the "newest"
        item_time = base_time - timedelta(microseconds=i)
        item_time_iso = item_time.isoformat()
        
        beer_data = {
            'url': url,
            'name': item.get('name'),
            'price': item.get('price'),
            'price_value': parse_price(item.get('price')),
            'image': item.get('image'),
            'stock_status': item.get('stock_status'),
            'shop': 'Arôme',
            'first_seen': item_time_iso, # FORCE CURRENT TIME
            'last_seen': current_time.isoformat(),
        }
        
        # Preserve other fields from existing record
        existing = existing_map.get(url)
        if existing:
            # Preserve untappd_url and any other metadata we might have
            if existing.get('untappd_url'):
                beer_data['untappd_url'] = existing.get('untappd_url')
            
        beers_to_upsert.append(beer_data)
        
    # 4. Upsert
    if beers_to_upsert:
        print(f"\n💾 Upserting {len(beers_to_upsert)} items with first_seen = NOW...")
        try:
            supabase.table('scraped_beers').upsert(beers_to_upsert, on_conflict='url').execute()
            print("  ✅ Success!")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            
    print("\n✨ Done.")

if __name__ == "__main__":
    asyncio.run(refresh_arome_top16())

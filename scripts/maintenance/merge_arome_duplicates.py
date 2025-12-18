
import os
import sys
import re
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

from app.scrapers.arome import normalize_url

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def merge_arome_duplicates():
    print("=" * 60)
    print("🍺 Arôme Duplicate Merge & Branding Update")
    print("=" * 60)
    
    # 1. Fetch all Arome/Arôme items
    print("\n📂 Fetching Arome/Arôme records...")
    all_items = []
    chunk_size = 1000
    start = 0
    while True:
        res = supabase.table('scraped_beers').select('*').or_('shop.eq.Arome,shop.eq.Arôme').range(start, start + chunk_size - 1).execute()
        if not res.data:
            break
        all_items.extend(res.data)
        if len(res.data) < chunk_size:
            break
        start += chunk_size
        
    print(f"  Found {len(all_items)} records.")
    
    # 2. Group by normalized URL
    print("\n🔍 Grouping by normalized URL...")
    groups = {}
    for item in all_items:
        norm = normalize_url(item['url'])
        if norm not in groups:
            groups[norm] = []
        groups[norm].append(item)
        
    print(f"  Total unique normalized URLs: {len(groups)}")
    
    # 3. Process each group
    to_upsert = []
    to_delete = []
    
    for norm_url, items in groups.items():
        # Identify the "best" data
        # - Oldest first_seen
        # - Newest last_seen
        # - Any untappd_url
        
        items.sort(key=lambda x: x['first_seen'])
        oldest_first_seen = items[0]['first_seen']
        
        items.sort(key=lambda x: x['last_seen'], reverse=True)
        newest_last_seen = items[0]['last_seen']
        
        # Merge untappd_url
        untappd_url = next((i['untappd_url'] for i in items if i.get('untappd_url')), None)
        
        # Use data from the newest item as base for other fields
        base_item = items[0] 
        
        merged_item = {
            'url': norm_url,
            'name': base_item['name'],
            'price': base_item['price'],
            'image': base_item['image'],
            'stock_status': base_item['stock_status'],
            'shop': 'Arôme',
            'first_seen': oldest_first_seen,
            'last_seen': newest_last_seen,
            'untappd_url': untappd_url
        }
        
        to_upsert.append(merged_item)
        
        # Identify URLs to delete (all original URLs that are NOT the norm_url)
        for i in items:
            if i['url'] != norm_url:
                to_delete.append(i['url'])
            elif i['shop'] == 'Arome':
                # Even if it IS the norm_url, we need to update 'Arome' -> 'Arôme'.
                # Upsert will handle this.
                pass

    # 4. Perform Updates
    if to_upsert:
        print(f"\n💾 Upserting {len(to_upsert)} merged Arôme records...")
        batch_size = 500
        for i in range(0, len(to_upsert), batch_size):
            batch = to_upsert[i:i+batch_size]
            print(f"  Upserting batch {i//batch_size + 1}...")
            supabase.table('scraped_beers').upsert(batch, on_conflict='url').execute()
            
    if to_delete:
        print(f"\n🗑️ Deleting {len(to_delete)} duplicate/unnormalized records...")
        batch_size = 500
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i:i+batch_size]
            print(f"  Deleting batch {i//batch_size + 1}...")
            supabase.table('scraped_beers').delete().in_('url', batch).execute()
            
    # 5. Handle gemini_data duplicates (optional but good practice)
    # Actually, if we delete from scraped_beers, gemini_data might have orphaned records.
    # But since gemini_data references the URL, we should probably merge it too.
    
    print("\n✨ Migration complete.")

if __name__ == "__main__":
    merge_arome_duplicates()

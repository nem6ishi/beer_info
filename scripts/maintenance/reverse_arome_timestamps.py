
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def reverse_arome_timestamps():
    print("=" * 60)
    print("🍺 Reversing Arôme Timestamps")
    print("=" * 60)
    
    # 1. Fetch all Arome beers ordered by first_seen
    print("\n📂 Loading all 'Arôme' beers...")
    all_beers = []
    chunk_size = 1000
    start = 0
    
    while True:
        res = supabase.table('scraped_beers') \
            .select('*') \
            .eq('shop', 'Arôme') \
            .order('first_seen', desc=False) \
            .range(start, start + chunk_size - 1) \
            .execute()
        
        if not res.data:
            break
        all_beers.extend(res.data)
        if len(res.data) < chunk_size:
            break
        start += chunk_size
    
    print(f"  Found {len(all_beers)} beers.")
    
    if not all_beers:
        print("❌ No Arôme beers found.")
        return

    # 2. Extract and reverse unique timestamps
    # Note: Many might be identical if they were bulk-inserted, 
    # but we preserved order with microseconds in some scripts.
    # To TRULY reverse the order of items, we should:
    # Get List of (URL, Timestamp)
    # Reverse the order of Timestamps across the URLs.
    
    print("\n🔄 Reversing timestamps...")
    all_timestamps = [item['first_seen'] for item in all_beers]
    reversed_timestamps = list(reversed(all_timestamps))
    
    # 3. Prepare updates
    updates = []
    for i, beer in enumerate(all_beers):
        item_update = beer.copy()
        item_update['first_seen'] = reversed_timestamps[i]
        updates.append(item_update)
        
    # 4. Batch update
    print(f"\n💾 Updating {len(updates)} Arôme beers...")
    batch_size = 500
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        print(f"  Updating batch {i // batch_size + 1} ({len(batch)} items)...")
        try:
            supabase.table('scraped_beers').upsert(batch, on_conflict='url').execute()
        except Exception as e:
            print(f"  ❌ Error: {e}")
            break
            
    print("\n✨ Done.")

if __name__ == "__main__":
    reverse_arome_timestamps()

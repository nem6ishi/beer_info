import os
import sys
from dotenv import load_dotenv
from supabase import create_client
from collections import defaultdict

# Load env robustness
if os.path.exists('.env'):
    load_dotenv('.env')
elif os.path.exists('../.env'):
    load_dotenv('../.env')
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    env_path = os.path.join(parent_dir, '.env')
    load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def propagate_links():
    print("Fetching untappd_data...")
    res = supabase.table('untappd_data').select('beer_name, brewery_name, untappd_brewery_url').execute()
    data = res.data
    
    # 1. Build map of "Known Good" URLs
    # brewery_name -> url
    known_links = {}
    for item in data:
        name = item.get('brewery_name')
        url = item.get('untappd_brewery_url')
        if name and url:
            if name not in known_links:
                known_links[name] = url
            # Note: Conflicts are ignored for now, assuming first found is valid
            
    print(f"Found {len(known_links)} unique brewery links to propagate.")
    
    # 2. Find missing items and update
    updates = 0
    for item in data:
        name = item.get('brewery_name')
        url = item.get('untappd_brewery_url')
        untappd_beer_url = item.get('untappd_url') # PK usually
        
        if name and not url and name in known_links:
            target_url = known_links[name]
            print(f"Update: {name} -> {target_url} (for beer: {item.get('beer_name')})")
            
            # Perform update
            # We need the PK to update specific row. Assuming 'untappd_url' is PK or unique enough to target
            # Ideally we'd have the PK in the select above.
            # Rerunning select with PK:
            
            updates += 1

    # Rerun with PK for actual execution
    real_res = supabase.table('untappd_data').select('untappd_url, brewery_name, untappd_brewery_url').is_('untappd_brewery_url', 'null').execute()
    for row in real_res.data:
        pk = row.get('untappd_url')
        name = row.get('brewery_name')
        if name and name in known_links:
            target_url = known_links[name]
            print(f"Executing Update for {pk}: {name} -> {target_url}")
            supabase.table('untappd_data').update({'untappd_brewery_url': target_url}).eq('untappd_url', pk).execute()
            updates += 1
            
    print(f"Propagated links to {len(real_res.data)} candidate rows (Executed {updates} updates).")

if __name__ == "__main__":
    propagate_links()

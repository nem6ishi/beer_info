import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.core.db import get_supabase_client
from backend.src.services.untappd.http_client import scrape_beer_details

def main():
    supabase = get_supabase_client()
    
    print("Querying for records with next.untappd.com/og/ images...")
    res = supabase.table('untappd_data').select('untappd_url, image_url, beer_name').ilike('image_url', '%next.untappd.com/og/%').execute()
    records = res.data or []
    
    print(f"Found {len(records)} records.")
    
    updated = 0
    for row in records:
        url = row['untappd_url']
        name = row.get('beer_name')
        print(f"\nProcessing: {name} ({url})")
        
        time.sleep(2) # rate limiting
        
        try:
            details = scrape_beer_details(url)
            new_label = details.get('untappd_label')
            
            if new_label and 'next.untappd.com/og/' not in new_label:
                print(f"  -> Found new label: {new_label}")
                supabase.table('untappd_data').update({'image_url': new_label}).eq('untappd_url', url).execute()
                updated += 1
            else:
                print(f"  -> No better label found. Got: {new_label}")
        except Exception as e:
            print(f"  -> Error: {e}")
            
    print(f"\nDone! Updated {updated} records.")

if __name__ == '__main__':
    main()

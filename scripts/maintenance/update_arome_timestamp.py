
import os
import sys
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Find the oldest first_seen in the table (excluding invalid dates if any)
print("Finding oldest first_seen...")
res = supabase.table('scraped_beers').select('first_seen').order('first_seen', desc=False).limit(1).execute()
if res.data:
    oldest = res.data[0]['first_seen']
    print(f"Current oldest timestamp: {oldest}")
    
    # Python isoformat parsing
    try:
        oldest_dt = datetime.fromisoformat(oldest.replace('Z', '+00:00'))
    except ValueError:
        # Handle cases where microsecond might be missing or other format
         oldest_dt = datetime.strptime(oldest, "%Y-%m-%dT%H:%M:%S.%f%z")

    # Make it 1 year older to be safe and clearly separate
    new_oldest = oldest_dt - timedelta(days=365)
    print(f"Target timestamp for arome: {new_oldest.isoformat()}")
    
    # 2. Update arome beers
    print("Updating 'arome' beers...")
    # Shop name is 'Arôme'
    target_shop = 'Arôme'
    check = supabase.table('scraped_beers').select('count', count='exact').eq('shop', target_shop).execute()
    print(f"Found {check.count} beers for shop '{target_shop}'.")
    
    if check.count > 0:
        # Update
        update_res = supabase.table('scraped_beers').update({'first_seen': new_oldest.isoformat()}).eq('shop', target_shop).execute()
        print(f"Update executed.")
        
        # Verify
        verify = supabase.table('scraped_beers').select('first_seen').eq('shop', target_shop).limit(1).execute()
        print(f"Verification - New {target_shop} timestamp: {verify.data[0]['first_seen']}")
    else:
        print(f"No '{target_shop}' beers found to update.")

else:
    print("No data found in scraped_beers.")

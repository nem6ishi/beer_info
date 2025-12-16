
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from app.services.untappd_searcher import get_untappd_url

# Configure logging to see searcher output
logging.basicConfig(level=logging.INFO)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def get_supabase_client():
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        sys.exit(1)
    return create_client(supabase_url, supabase_key)


def compare_timestamps():
    supabase = get_supabase_client()
    


    # Fetch Ao-oni
    ao_oni_res = supabase.table('beer_info_view').select('*').ilike('name', '%青鬼ピルスナー%').limit(1).execute()
    
    print("--- Ao-oni ---")
    for item in ao_oni_res.data:
        print(f"Name: {item['name']}")
        print(f"Brewery (EN): {item.get('brewery_name_en')}")
        print(f"Brewery (JP): {item.get('brewery_name_jp')}")
        print(f"Beer Name (EN): {item.get('beer_name_en')}")
        print(f"Beer Name (JP): {item.get('beer_name_jp')}")

    # Fetch Topa Topa item to find Untappd URL
    topa_search = supabase.table('beer_info_view').select('untappd_url').ilike('name', '%Topa Topa Good Good Hazy DIPA%').limit(1).execute()
    
    if not topa_search.data:
        print("Topa Topa item not found")
        return

    untappd_url = topa_search.data[0]['untappd_url']
    print(f"\nTopa Topa Untappd URL: {untappd_url}")

    if not untappd_url:
        print("Topa Topa has no Untappd URL (so it shouldn't be grouped?)")
        # Check if there are other items with same name?
        return

    # Fetch ALL items in this group
    group_res = supabase.table('beer_info_view').select('name, first_seen').eq('untappd_url', untappd_url).order('first_seen', desc=True).execute()

    print("\n--- Topa Topa Group Items ---")
    for item in group_res.data:
        print(f"Name: {item['name']}")
        print(f"Time: {item['first_seen']}")

if __name__ == "__main__":
    compare_timestamps()


import os
import sys
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_messorem():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("--- Breweries Table ---")
    res = supabase.table('breweries').select('*').ilike('name_en', '%Messorem%').execute()
    if res.data:
        for b in res.data:
            print(f"ID: {b['id']}")
            print(f"Name: {b['name_en']}")
            print(f"Location: {b['location']}")
            print(f"URL: {b['untappd_url']}")
            print(f"Updated: {b['updated_at']}")
    else:
        print("Not found in breweries table.")

    print("\n--- Untappd Data Table (Recent 5) ---")
    res = supabase.table('untappd_data').select('beer_name, brewery_name, untappd_brewery_url').ilike('brewery_name', '%Messorem%').limit(5).execute()
    if res.data:
        for b in res.data:
            print(f"Beer: {b['beer_name']}")
            print(f"Brewery: {b['brewery_name']}")
            print(f"Brewery URL: {b['untappd_brewery_url']}")
    else:
        print("Not found in untappd_data table.")

if __name__ == "__main__":
    check_messorem()

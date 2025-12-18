import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load env robustness
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # beer_info
env_path = os.path.join(parent_dir, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"Loaded env from: {env_path}")
else:
    print(f"Warning: .env not found at {env_path}")
    # Try default
    load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL:
    print("Error: SUPABASE_URL not set")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_wakasaimo():
    print("Searching for 'Wakasaimo' in beer_info_view...")
    try:
        res = supabase.table('beer_info_view').select('*').ilike('name', '%Wakasaimo%').execute()
        
        if not res.data:
            print("No results found for %Wakasaimo%")
            # Try Japanese
            print("Searching for '鬼伝説'...")
            res = supabase.table('beer_info_view').select('*').ilike('name', '%鬼伝説%').execute()

        print(f"Found {len(res.data)} records.")
        for item in res.data:
            print(f"- Name: {item.get('name')}")
            print(f"  Untappd URL: {item.get('untappd_url')}")
            print(f"  Brewery URL: {item.get('untappd_brewery_url')}")
            print(f"  Enriched Loc: {item.get('brewery_location')}")
            print("-" * 20)


    except Exception as e:
        print(f"Error: {e}")

    print("\nChecking 'breweries' table directly...")
    try:
        url = "https://untappd.com/w/wakasaimo-honpo/12554"
        res = supabase.table('breweries').select('*').eq('untappd_url', url).execute()
        if res.data:
            print(f"Found brewery record: {res.data[0]}")
            print(f"Logo URL: {res.data[0].get('logo_url')}")
        else:
            print(f"Brewery record NOT FOUND for {url}")
    except Exception as e:
        print(f"Error checking breweries: {e}")


if __name__ == "__main__":
    check_wakasaimo()

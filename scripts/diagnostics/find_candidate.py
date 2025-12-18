
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

def find_candidate():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("--- Searching for Candidate in Scraped Data ---")
    res = supabase.table('beer_info_view').select('name, url, shop').ilike('name', '%Black Demon%').execute()
    if res.data:
        for b in res.data:
            print(f"Name: {b['name']}")
            print(f"Shop: {b['shop']}")
            print(f"URL: {b['url']}")
    else:
        print("Not found in beer_info_view.")
        
    print("\n--- Searching for 'Yoho' ---")
    res = supabase.table('beer_info_view').select('name').ilike('name', '%Yoho%').limit(5).execute()
    for b in res.data:
        print(f"Match: {b['name']}")

if __name__ == "__main__":
    find_candidate()

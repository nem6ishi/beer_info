
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

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

def clear_nupuru():
    supabase = get_supabase_client()
    
    # 1. Find Nupuru URL in scraped_beers
    # Use name match to find the url (product page url)
    res = supabase.table('scraped_beers').select('url, name').ilike('name', '%ヌプルペッペールエール%').execute()
    
    if not res.data:
        print("Nupuru not found.")
        return

    for item in res.data:
        print(f"Clearing untappd_url for: {item['name']}")
        supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', item['url']).execute()
        # Also clear gemini_data persistence
        supabase.table('gemini_data').update({'untappd_url': None}).eq('url', item['url']).execute()
        print("Cleared from scraped_beers and gemini_data.")

if __name__ == "__main__":
    clear_nupuru()


import os
import sys
from supabase import create_client
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def get_supabase_client():
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    return create_client(supabase_url, supabase_key)

def clear_oni_invalid():
    supabase = get_supabase_client()
    res = supabase.table('beer_info_view').select('url, name, untappd_url').ilike('name', '%鬼伝説%').execute()
    
    count_cleared = 0
    
    for item in res.data:
        url = item['untappd_url']
        if url and '/search?q=' in url:
            print(f"Clearing invalid URL for: {item['name']}")
            # Clear from scraped_beers and gemini_data
            supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', item['url']).execute()
            supabase.table('gemini_data').update({'untappd_url': None}).eq('url', item['url']).execute()
            count_cleared += 1
            
    print(f"Cleared {count_cleared} items.")

if __name__ == "__main__":
    clear_oni_invalid()

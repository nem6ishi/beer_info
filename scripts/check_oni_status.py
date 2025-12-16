
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

def check_oni():
    supabase = get_supabase_client()
    res = supabase.table('beer_info_view').select('name, untappd_url').ilike('name', '%鬼伝説%').execute()
    
    count_search = 0
    count_valid = 0
    count_missing = 0
    
    for item in res.data:
        url = item['untappd_url']
        if not url:
            count_missing += 1
            print(f"Missing: {item['name']}")
        elif '/search?q=' in url:
            count_search += 1
            # print(f"Search URL: {item['name']} -> {url}")
        elif '/b/' in url:
            count_valid += 1
            # print(f"Valid URL: {item['name']} -> {url}")
        else:
            print(f"Unknown URL: {item['name']} -> {url}")

    print(f"Total: {len(res.data)}")
    print(f"Valid: {count_valid}")
    print(f"Search (Invalid): {count_search}")
    print(f"Missing: {count_missing}")

if __name__ == "__main__":
    check_oni()

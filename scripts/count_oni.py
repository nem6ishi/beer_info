
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

def count_oni():
    supabase = get_supabase_client()
    res = supabase.table('beer_info_view').select('name', count='exact').ilike('name', '%鬼伝説%').execute()
    print(f"Count of products with '鬼伝説': {res.count}")

if __name__ == "__main__":
    count_oni()

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

if os.path.exists('.env'):
    load_dotenv('.env')
elif os.path.exists('../.env'):
    load_dotenv('../.env')
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    env_path = os.path.join(parent_dir, '.env')
    load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def count():
    # Fetch all non-null brewery URLs
    res = supabase.table('untappd_data').select('untappd_brewery_url').not_.is_('untappd_brewery_url', 'null').execute()
    total = len(res.data)
    unique = set(r['untappd_brewery_url'] for r in res.data)
    
    print(f"Total rows with brewery URL: {total}")
    print(f"Unique brewery URLs: {len(unique)}")
    
    if len(unique) < 20:
        print("Sample URLs:")
        for u in unique:
            print(f" - {u}")

if __name__ == "__main__":
    count()

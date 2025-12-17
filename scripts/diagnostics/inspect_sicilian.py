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

def check():
    url = 'https://untappd.com/b/wakasaimo-honpo-oni-densetsu-sicilian-rouge/154539'
    res = supabase.table('untappd_data').select('*').eq('untappd_url', url).execute()
    if res.data:
        print(f"Brewery Name: '{res.data[0].get('brewery_name')}'")
        print(f"Brewery URL (FK): '{res.data[0].get('untappd_brewery_url')}'")
    else:
        print("Record not found.")

if __name__ == "__main__":
    check()

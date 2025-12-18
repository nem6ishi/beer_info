
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

target_urls = [
    "https://untappd.com/CRAFTROCK",
    "https://untappd.com/w/yuya-boys/446175"
]

print("Checking 'breweries' table by URL...")
for url in target_urls:
    res = supabase.table('breweries').select('*').eq('untappd_url', url).execute()
    data = res.data
    if data:
        print(f"\n--- Found URL: {url} ---")
        item = data[0]
        print(f"  Name: {item.get('name_en')}")
        print(f"  Logo: {item.get('logo_url')}")
    else:
        print(f"\n--- URL NOT FOUND: {url} ---")

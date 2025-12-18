
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Get all unique brewery URLs from untappd_data
print("Fetching unique URLs from untappd_data...")
res = supabase.table('untappd_data').select('untappd_brewery_url').not_.is_('untappd_brewery_url', 'null').execute()
untappd_urls = set(item['untappd_brewery_url'] for item in res.data)
print(f"Total unique brewery URLs in untappd_data: {len(untappd_urls)}")

# Get all URLs from breweries table
print("Fetching URLs from breweries table...")
res = supabase.table('breweries').select('untappd_url').execute()
enriched_urls = set(item['untappd_url'] for item in res.data)
print(f"Total enriched breweries: {len(enriched_urls)}")

missing = untappd_urls - enriched_urls
print(f"Missing (unenriched) breweries: {len(missing)}")

if "https://untappd.com/CRAFTROCK" in missing:
    print("Confirmed: https://untappd.com/CRAFTROCK is missing.")
if "https://untappd.com/w/yuya-boys/446175" in missing:
    print("Confirmed: https://untappd.com/w/yuya-boys/446175 is missing.")

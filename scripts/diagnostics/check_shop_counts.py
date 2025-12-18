
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Listing distinct shops in scraped_beers...")
res = supabase.table('scraped_beers').select('shop').execute()
shops = set(item['shop'] for item in res.data)
print(f"Found shops: {shops}")

# Check if any have 'Arome' (without accent)
res_plain = supabase.table('scraped_beers').select('count', count='exact').eq('shop', 'Arome').execute()
print(f"Count of 'Arome' (plain): {res_plain.count}")

res_accent = supabase.table('scraped_beers').select('count', count='exact').eq('shop', 'Arôme').execute()
print(f"Count of 'Arôme' (accent): {res_accent.count}")

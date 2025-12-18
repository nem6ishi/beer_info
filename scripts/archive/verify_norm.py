import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: credentials missing")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Checking scraped_beers table...")
try:
    res = supabase.table('scraped_beers').select('url').limit(1).execute()
    print(f"✅ scraped_beers access OK. Rows: {len(res.data)}")
except Exception as e:
    print(f"❌ scraped_beers error: {e}")

print("Checking beer_info_view...")
try:
    res = supabase.table('beer_info_view').select('url, brewery_name_en').limit(1).execute()
    print(f"✅ beer_info_view access OK. Rows: {len(res.data)}")
except Exception as e:
    print(f"❌ beer_info_view error: {e}")

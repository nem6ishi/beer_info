
import unicodedata

names = ["Arôme"]
for name in names:
    nfc = unicodedata.normalize('NFC', name)
    nfd = unicodedata.normalize('NFD', name)
    print(f"Name: {name}")
    print(f"  NFC: {nfc.encode('utf-8').hex()} ({len(nfc)})")
    print(f"  NFD: {nfd.encode('utf-8').hex()} ({len(nfd)})")
    print(f"  Equal? {nfc == nfd}")

# Check what's in DB
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("\nFetching shop from DB to check encoding...")
res = supabase.table('scraped_beers').select('shop').eq('shop', 'Arôme').limit(1).execute()
if res.data:
    db_name = res.data[0]['shop']
    print(f"DB Name: {db_name}")
    print(f"  NFC: {unicodedata.normalize('NFC', db_name).encode('utf-8').hex()}")
    print(f"  NFD: {unicodedata.normalize('NFD', db_name).encode('utf-8').hex()}")
    print(f"  Actual: {db_name.encode('utf-8').hex()}")
else:
    print("Could not find 'Arôme' in DB with exact match.")
    
# Try finding with like
print("\nTrying ilike %Ar%me%...")
res_like = supabase.table('scraped_beers').select('shop').ilike('shop', '%Ar%me%').limit(1).execute()
if res_like.data:
    db_name = res_like.data[0]['shop']
    print(f"Found with ilike: {db_name}")
    print(f"  Actual bytes: {db_name.encode('utf-8').hex()}")

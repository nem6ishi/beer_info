
import os
import sys
from supabase import create_client
import json

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Fetching latest 3 beers...")
res = supabase.table('scraped_beers').select('name, price, stock_status, shop, first_seen, url').order('first_seen', desc=True).limit(3).execute()

if res.data:
    for i, item in enumerate(res.data, 1):
        print(f"\n[{i}] {item['name']}")
        print(f"    Shop: {item['shop']}")
        print(f"    Price: {item['price']}")
        print(f"    Stock: {item['stock_status']}")
        print(f"    First Expected: {item['first_seen']}")
        print(f"    URL: {item['url']}")
else:
    print("No beers found.")


import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# Add parent directory to path to import app modules if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

target_breweries = ["Craftrock Brewing", "Yuya Boys"]

print("Checking 'untappd_data' for target breweries...")
for name in target_breweries:
    # Use ilike for case-insensitive partial match
    res = supabase.table('untappd_data').select('*').ilike('brewery_name', f"%{name}%").execute()
    data = res.data
    if data:
        print(f"\n--- Results for '{name}' in untappd_data ---")
        for item in data[:3]: # Show top 3
            print(f"  Beer: {item.get('beer_name')}")
            print(f"  Brewery: {item.get('brewery_name')}")
            print(f"  URL: {item.get('untappd_brewery_url')}")
    else:
        print(f"\nNo results found for '{name}' in untappd_data")

print("\n\nChecking 'breweries' table...")
for name in target_breweries:
    res = supabase.table('breweries').select('*').ilike('name_en', f"%{name}%").execute()
    data = res.data
    if data:
        print(f"\n--- Results for '{name}' in breweries ---")
        for item in data:
            print(f"  Name: {item.get('name_en')}")
            print(f"  URL: {item.get('untappd_url')}")
            print(f"  Logo: {item.get('logo_url')}")
            print(f"  Location: {item.get('location')}")
    else:
        print(f"\nNo results found for '{name}' in breweries table")

import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# Load env
load_dotenv('.env')

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

def check_beer():
    # Search for the beer
    term = "Good Good Hazy DIPA"
    print(f"Searching for '{term}'...")
    
    res = supabase.table('beer_info_view').select('*').ilike('name', f'%{term}%').execute()
    
    if not res.data:
        print("No results found.")
        return

    print(f"Found {len(res.data)} items.")
    for item in res.data:
        print("-" * 40)
        print(f"Name: {item.get('name')}")
        print(f"Brewery: {item.get('brewery')}")
        print(f"Shop: {item.get('shop')}")
        print(f"Untappd URL: {item.get('untappd_url')}")
        print(f"Untappd Image: {item.get('untappd_image')}") # Check column name, might be 'beer_image' or 'untappd_label' in view
        print(f"Item Image: {item.get('image')}")
        print(f"Price: {item.get('price')}")

if __name__ == "__main__":
    check_beer()

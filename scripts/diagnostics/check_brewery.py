import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from scripts.utils.script_utils import setup_script

def check_brewery():
    supabase, logger = setup_script("CheckBrewery")
    
    target_brewery_url = "https://untappd.com/w/and-beer/385368"
    
    logger.info(f"Checking breweries for {target_brewery_url}...")
    
    response = supabase.table('breweries').select("*").eq('untappd_url', target_brewery_url).execute()
    
    if response.data:
        print(f"Brewery FOUND: {response.data[0]}")
    else:
        print("Brewery NOT found. Need to enrich/add it.")

if __name__ == "__main__":
    check_brewery()

import os
import sys
import argparse

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.utils.script_utils import setup_script

def find_beer(name_query):
    supabase, logger = setup_script("FindBeer")
    
    logger.info(f"Searching for '{name_query}'...")
    
    # 1. Search scraped_beers
    res = supabase.table('beer_info_view').select('*').ilike('name', f"%{name_query}%").execute()
    
    logger.info(f"Found {len(res.data)} matching beers")
    
    for beer in res.data:
        print("---")
        print(f"Name: {beer.get('name')}")
        print(f"URL: {beer.get('url')}")
        print(f"Current Untappd URL: {beer.get('untappd_url')}")
        print(f"Untappd JSON: {beer.get('untappd_json')}") # Check if details were scraped

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('name', type=str, help='Name to search')
    args = parser.parse_args()
    find_beer(args.name)

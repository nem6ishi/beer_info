import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from scripts.utils.script_utils import setup_script

def find_beer():
    supabase, logger = setup_script("FindBeer")
    
    logger.info("Searching for 'And Beer' or 'Tamiru'...")
    
    # Simple like query on scraped_beers
    # We want to check name
    
    response = supabase.table('scraped_beers').select("*").ilike('name', '%Tamiru%').execute()
    
    beers = response.data
    logger.info(f"Found {len(beers)} beers matching 'Tamiru'")
    
    for beer in beers:
        print(f"---")
        print(f"Name: {beer.get('name')}")
        print(f"URL: {beer.get('url')}")
        print(f"Shop: {beer.get('shop')}")
        print(f"Current Untappd URL: {beer.get('untappd_url')}")
        
    print("\nAlso checking 'And Beer'...")
    response2 = supabase.table('scraped_beers').select("*").ilike('name', '%And Beer%').execute()
    beers2 = response2.data
    logger.info(f"Found {len(beers2)} beers matching 'And Beer'")
    
    for beer in beers2:
        print(f"---")
        print(f"Name: {beer.get('name')}")
        print(f"URL: {beer.get('url')}")
        print(f"Shop: {beer.get('shop')}")
        print(f"Current Untappd URL: {beer.get('untappd_url')}")

if __name__ == "__main__":
    find_beer()

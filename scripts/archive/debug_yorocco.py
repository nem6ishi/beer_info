import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import get_untappd_url

def debug_yorocco():
    # Simulate the inputs that are failing
    brewery_jp = "ヨロッコ" 
    beer_name = "YEXIT" # Often scraped name is english-ish
    
    print(f"Searching for Brewery: {brewery_jp}, Beer: {beer_name}")
    url = get_untappd_url(brewery_jp, beer_name)
    print(f"Result URL: {url}")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    debug_yorocco()

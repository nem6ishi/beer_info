import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import scrape_brewery_details

def debug_leffe_brewery():
    url = "https://untappd.com/w/abbaye-de-leffe/5"
    print(f"Scraping Brewery: {url}...")
    
    details = scrape_brewery_details(url)
    
    print("\n--- Extraction Results ---")
    print(f"Name:     '{details.get('brewery_name')}'")
    print(f"Location: '{details.get('location')}'")
    print(f"Type:     '{details.get('brewery_type')}'")
    print("-" * 30)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    debug_leffe_brewery()

import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import scrape_beer_details

def debug_leffe():
    url = "https://untappd.com/b/abbaye-de-leffe-leffe-brune-bruin/5940"
    print(f"Scraping {url}...")
    
    details = scrape_beer_details(url)
    
    print("\n--- Extraction Results ---")
    print(f"Brewery Name: '{details.get('untappd_brewery_name')}'")
    print(f"Brewery URL:  '{details.get('untappd_brewery_url')}'")
    print("-" * 30)

if __name__ == "__main__":
    debug_leffe()

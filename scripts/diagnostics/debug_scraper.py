import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from app.services.untappd_searcher import scrape_beer_details

def debug_scraper():
    # The URL that had the issue
    url = "https://untappd.com/b/and-beer-tamiru-tadesse-coffee-ale/6488346"
    print(f"Scraping {url}...")
    
    details = scrape_beer_details(url)
    
    print("\n--- Extracted Details ---")
    for k, v in details.items():
        print(f"{k}: {v}")
        
    print("\n--- Checks ---")
    expected_brewery_url = "https://untappd.com/w/and-beer/385368"
    if details.get('untappd_brewery_url') == expected_brewery_url:
        print("MATCH: Brewery URL matches expected.")
    else:
        print(f"MISMATCH: Expected {expected_brewery_url}, got {details.get('untappd_brewery_url')}")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    debug_scraper()

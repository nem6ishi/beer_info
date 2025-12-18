
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import scrape_brewery_details

# Configure logging to see output
logging.basicConfig(level=logging.INFO)

target_urls = [
    "https://untappd.com/CRAFTROCK",
    "https://untappd.com/w/yuya-boys/446175"
]

print("Testing scraper on target URLs...")
for url in target_urls:
    print(f"\n--- Scraping {url} ---")
    details = scrape_brewery_details(url)
    print(f"Result: {details}")

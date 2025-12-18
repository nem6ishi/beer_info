import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import scrape_beer_details
from scripts.utils.script_utils import setup_script

def debug_scrape(url):
    _, logger = setup_script("DebugScrape")
    logger.info(f"Scraping: {url}")
    details = scrape_beer_details(url)
    print("--- SCRAPE RESULT ---")
    for k, v in details.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    debug_scrape("https://untappd.com/b/yorocco-beer-akizuki-hoppy-farmhouse-ale/1258673")


import sys
import os

# Add app directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.untappd_searcher import search_brewery, scrape_brewery_details
import logging

logging.basicConfig(level=logging.INFO)

def test_brewery(name):
    print(f"Testing brewery: {name}")
    url = search_brewery(name)
    print(f"Found URL: {url}")
    if url:
        details = scrape_brewery_details(url)
        print(f"Details: {details}")
    else:
        print("Failed to find URL")

if __name__ == "__main__":
    test_brewery("Craftrock Brewing")
    test_brewery("Yuya Boys")

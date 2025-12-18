
import logging
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import get_untappd_url, validate_brewery_match
import requests
from bs4 import BeautifulSoup
import urllib.parse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_search():
    beer_name = "Weekender"
    brewery_name = "Topa Topa Brewing"
    
    print(f"--- Debugging Search: Beer='{beer_name}' Brewery='{brewery_name}' ---")
    
    # 1. Simulate the exact query construction from untappd_searcher.py
    query = f"{beer_name} {brewery_name}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://untappd.com/search?q={encoded_query}"
    
    print(f"Generated URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    resp = requests.get(url, headers=headers)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        soup = BeautifulSoup(resp.text, 'lxml')
        results = soup.select('.beer-item')
        print(f"Found {len(results)} results.")
        
        for i, res in enumerate(results[:5]):
            print(f"\n[Result {i+1}]")
            
            name_tag = res.select_one('.name a')
            beer_res_name = name_tag.get_text(strip=True) if name_tag else "N/A"
            href = name_tag.get('href') if name_tag else "N/A"
            
            brewery_tag = res.select_one('.brewery')
            brewery_res_name = brewery_tag.get_text(strip=True) if brewery_tag else "N/A"
            
            print(f"  Beer: {beer_res_name}")
            print(f"  Brewery: {brewery_res_name}")
            print(f"  URL: https://untappd.com{href}")
            
            # Test Validation
            is_match = validate_brewery_match(res, brewery_name)
            print(f"  Validation Result: {is_match}")
            
            if is_match:
                print("  ✅ THIS WOULD BE SELECTED")
    
    # Run the full function to see if fallback logic does anything differently
    print("\n\n--- Running get_untappd_url via Module ---")
    final_url = get_untappd_url(brewery_name, beer_name)
    print(f"Final Outcome: {final_url}")

if __name__ == "__main__":
    debug_search()

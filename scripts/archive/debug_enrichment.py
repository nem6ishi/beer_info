
import asyncio
import logging
import sys
import os

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import get_untappd_url

# Configure Logging
logging.basicConfig(level=logging.INFO) # INFO should show "Searching..."
logger = logging.getLogger("untappd_searcher")
logger.setLevel(logging.DEBUG) # DEBUG shows validation failure

def test_enrichment():
    brewery_en = None
    brewery_jp = "鬼伝説"
    beer_name_jp = "ヌプルペッペールエール"
    beer_name_en = None # In DB it was null? Actually let's assume NULL based on output "Name: 【ヌプル...】" usually implies combined or JP name dominance

    # Based on compare_timestamps.py output: 
    # Name: 【ヌプルペッペールエール/鬼伝説】 (This looks like scraped name, maybe beer_name_en is None)
    
    print(f"Testing search for: {brewery_jp} - {beer_name_jp}")
    
    # Logic from scripts/enrich_untappd.py
    # untappd_url = get_untappd_url(brewery, beer_name, beer_name_jp=beer_name_jp_clean)
    
    # We pass brewery_jp as primary brewery name if EN is missing
    brewery = brewery_en or brewery_jp
    
    url = get_untappd_url(brewery, beer_name_en, beer_name_jp=beer_name_jp)
    print(f"Result URL: {url}")

if __name__ == "__main__":
    test_enrichment()

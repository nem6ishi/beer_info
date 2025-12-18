
import asyncio
import os
import sys
import logging

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.gemini_extractor import GeminiExtractor
from app.services.untappd_searcher import get_untappd_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_messorem():
    enricher = GeminiExtractor()
    
    # The problematic item name
    raw_name = "メッソレム トリプルトンブ / MESSOREM Triple Tombe　≪12/20-21入荷予定≫"
    
    print(f"--- Debugging Gemini Extraction for: {raw_name} ---")
    
    # Test 1: No Hint (Simulating if Messorem wasn't detected)
    print("\n[Test 1: No Hint]")
    try:
        result = await enricher.extract_info(raw_name, known_brewery=None)
        print(f"  Brewery (EN): {result.get('brewery_name_en')}")
        print(f"  Beer (EN):    {result.get('beer_name_en')}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: With Hint (Simulating if validation matched it)
    print("\n[Test 2: With Hint 'Messorem']")
    try:
        result = await enricher.extract_info(raw_name, known_brewery="Messorem")
        print(f"  Brewery (EN): {result.get('brewery_name_en')}")
        print(f"  Beer (EN):    {result.get('beer_name_en')}")
        
        if result.get('brewery_name_en') == "Messorem" or result.get('brewery_name_en') == "MESSOREM":
             print("  ✅ Fixed with hint!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_messorem())

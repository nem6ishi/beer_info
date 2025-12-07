import asyncio
import json
import os
import datetime
import time
from typing import List, Dict, Optional

from . import beervolta
from . import chouseiya
from . import ichigo_ichie
from ..services.gemini_extractor import GeminiExtractor
from ..services.untappd_searcher import get_untappd_url, scrape_beer_details

# Define paths relative to this file or project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "beers.json")

def load_existing_data(filepath: str) -> Dict[str, dict]:
    """Loads existing beer data from JSON file into a dict keyed by URL."""
    existing_data = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                old_list = json.load(f)
                for item in old_list:
                    if 'url' in item:
                        existing_data[item['url']] = item
        except Exception as e:
            print(f"Error loading existing data: {e}")
    return existing_data

def save_data(data: List[dict], filepath: str):
    """Saves the merged beer list to a JSON file."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Saved merged data to {filepath}")
    except Exception as e:
        print(f"Error saving data: {e}")

async def enrich_with_gemini(new_item: dict, existing_item: Optional[dict], extractor: GeminiExtractor) -> dict:
    """Enriches beer item with Gemini (brewery/beer name extraction). Preserves history if existing."""
    current_time_str = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    
    if existing_item:
        # Preserve history
        new_item['first_seen'] = existing_item.get('first_seen', current_time_str)
        new_item['last_seen'] = current_time_str
        
        # Use existing extracted names if available to save API calls
        if existing_item.get('brewery_name_en') or existing_item.get('brewery_name_jp'):
             new_item['brewery_name_jp'] = existing_item.get('brewery_name_jp')
             new_item['brewery_name_en'] = existing_item.get('brewery_name_en')
             new_item['beer_name_jp'] = existing_item.get('beer_name_jp')
             new_item['beer_name_en'] = existing_item.get('beer_name_en')
             return new_item # Already enriched

    # New item or needs enrichment
    if not existing_item:
        new_item['first_seen'] = current_time_str
        new_item['last_seen'] = current_time_str

    # Call Gemini
    enriched_info = await extractor.extract_info(new_item['name'])
    if enriched_info:
        if enriched_info.get('brewery_name_jp'): new_item['brewery_name_jp'] = enriched_info['brewery_name_jp']
        if enriched_info.get('brewery_name_en'): new_item['brewery_name_en'] = enriched_info['brewery_name_en']
        if enriched_info.get('beer_name_jp'): new_item['beer_name_jp'] = enriched_info['beer_name_jp']
        if enriched_info.get('beer_name_en'): new_item['beer_name_en'] = enriched_info['beer_name_en']
    
    return new_item

async def enrich_with_untappd(item: dict, existing_item: Optional[dict]):
    """Enriches beer item with Untappd URL and details (async version)."""
    # 1. Get or Search URL
    untappd_url = None
    if existing_item and existing_item.get('untappd_url'):
        untappd_url = existing_item['untappd_url']
        item['untappd_url'] = untappd_url
    
    if not untappd_url:
        search_brewery = item.get('brewery_name_en') or item.get('brewery_name_jp')
        search_beer = item.get('beer_name_en') or item.get('beer_name_jp')
        
        if search_brewery or search_beer:
            try:
                untappd_url = get_untappd_url(search_brewery, search_beer)
                if untappd_url:
                    item['untappd_url'] = untappd_url
                await asyncio.sleep(2)  # Rate limit (async)
            except Exception as e:
                print(f"Error calling Untappd search: {e}")

    # 2. Scrape Details if URL is valid
    # Re-check item for untappd_url in case we just found it
    current_url = item.get('untappd_url')
    if current_url and "untappd.com/b/" in current_url:
         try:
             details = scrape_beer_details(current_url)
             if details:
                 item.update(details)
             await asyncio.sleep(1)  # Rate limit (async)
         except Exception as e:
             print(f"Error scraping Untappd details: {e}")


async def run_scrapers(limit: int = None):
    print("Starting scrapers orchestration...")
    
    # Load Data
    existing_data = load_existing_data(OUTPUT_FILE)

    # Scrape
    print("--- Running Scrapers in Parallel ---")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit),
        chouseiya.scrape_chouseiya(limit=limit),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit),
        return_exceptions=True
    )
    
    # Process Results
    new_scraped_items = []
    names_collected = []
    
    # Unpack results
    for res in results:
        if isinstance(res, list):
            new_scraped_items.extend(res)
            names_collected.append(f"{len(res)} items")
        elif isinstance(res, Exception):
            print(f"Scraper error: {res}")
            
    print(f"Collected total {len(new_scraped_items)} items from sources.")

    merged_list = []
    extractor = GeminiExtractor()

    # Process enrichment in batches for better performance
    async def enrich_item(new_item):
        url = new_item.get('url')
        if not url:
            return None
        
        existing_item = existing_data.get(url)
        
        # Enrichment (Gemini)
        enriched = await enrich_with_gemini(new_item, existing_item, extractor)
        
        # Enrichment (Untappd) - now async
        await enrich_with_untappd(enriched, existing_item)
        
        return enriched

    # Process all items concurrently (Gemini has built-in rate limiting)
    print("Enriching items with Gemini and Untappd...")
    enriched_items = await asyncio.gather(*[enrich_item(item) for item in new_scraped_items])
    
    # Filter out None values
    merged_list = [item for item in enriched_items if item is not None]
    
    print(f"Total merged beers: {len(merged_list)}")
    save_data(merged_list, OUTPUT_FILE)


if __name__ == "__main__":
    asyncio.run(run_scrapers())

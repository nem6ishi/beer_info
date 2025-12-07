"""
Scraping service
Runs scrapers without enrichment
"""
import asyncio
import json
import os
import datetime
from typing import List, Dict

from app.scrapers import beervolta, chouseiya, ichigo_ichie

# app/services/scraper_service.py -> app/services -> app -> root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "beers.json")


def load_existing_data(filepath: str) -> Dict[str, dict]:
    """Load existing beer data as a dict with URL as key"""
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
    """Save merged beer list"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"✅ Saved {len(data)} beers to {filepath}")
    except Exception as e:
        print(f"❌ Error saving data: {e}")


async def scrape_only(limit: int = None):
    """Execute scraping only (no enrichment)"""
    print("=" * 60)
    print("🍺 Starting SCRAPE-ONLY mode (no Gemini/Untappd)")
    print("=" * 60)
    
    existing_data = load_existing_data(OUTPUT_FILE)
    print(f"📂 Loaded {len(existing_data)} existing beers")

    print("\n🔍 Running scrapers in parallel...")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit),
        chouseiya.scrape_chouseiya(limit=limit),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit),
        return_exceptions=True
    )
    
    new_scraped_items = []
    for i, res in enumerate(results):
        scraper_names = ['BeerVolta', 'Chouseiya', 'Ichigo Ichie']
        if isinstance(res, list):
            print(f"  ✅ {scraper_names[i]}: {len(res)} items")
            new_scraped_items.extend(res)
        elif isinstance(res, Exception):
            print(f"  ❌ {scraper_names[i]}: Error - {res}")
            
    print(f"\n📊 Total scraped: {len(new_scraped_items)} items")

    current_time_str = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    merged_dict = {}
    new_count = 0
    updated_count = 0
    preserved_count = 0

    for beer in existing_data.values():
        url = beer.get('url')
        if url:
            merged_dict[url] = beer.copy()

    for index, new_item in enumerate(new_scraped_items):
        url = new_item.get('url')
        if not url:
            continue
        
        new_item['scrape_order'] = index
        new_item['scrape_timestamp'] = current_time_str
        
        if url in merged_dict:
            existing_item = merged_dict[url]
            
            prev_stock = (existing_item.get('stock_status') or '').lower()
            new_stock = (new_item.get('stock_status') or '').lower()
            
            was_sold_out = 'sold' in prev_stock or 'out' in prev_stock
            is_now_available = not ('sold' in new_stock or 'out' in new_stock)
            
            if was_sold_out and is_now_available:
                existing_item['restocked_at'] = current_time_str
                existing_item['available_since'] = current_time_str
                print(f"  🔄 Restock detected: {new_item.get('name', 'Unknown')[:50]}")
            elif not existing_item.get('available_since'):
                existing_item['available_since'] = existing_item.get('first_seen', current_time_str)
            
            existing_item['last_seen'] = current_time_str
            existing_item['scrape_order'] = new_item['scrape_order']
            existing_item['scrape_timestamp'] = new_item['scrape_timestamp']
            existing_item['price'] = new_item.get('price')
            existing_item['stock_status'] = new_item.get('stock_status')
            existing_item['image'] = new_item.get('image')
            existing_item['name'] = new_item.get('name')
            
            updated_count += 1
        else:
            new_item['first_seen'] = current_time_str
            new_item['last_seen'] = current_time_str
            new_item['available_since'] = current_time_str
            merged_dict[url] = new_item
            new_count += 1

    preserved_count = len(merged_dict) - new_count - updated_count
    
    merged_list = list(merged_dict.values())
    
    print(f"\n📈 Statistics:")
    print(f"  🆕 New beers: {new_count}")
    print(f"  🔄 Updated beers: {updated_count}")
    print(f"  💾 Preserved beers (not in current scrape): {preserved_count}")
    print(f"  📦 Total beers: {len(merged_list)}")
    
    save_data(merged_list, OUTPUT_FILE)
    
    print("\n" + "=" * 60)
    print("✨ Scraping completed!")
    print("💡 Next steps:")
    print("   - Run 'python -m app.cli enrich' to enrich data")
    print("=" * 60)

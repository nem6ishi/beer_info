"""
Sequential enrichment service
Processing 1 beer at a time:
1. Extract Brewery/Beer name with Gemini
2. Get Untappd info
3. Update Brewery DB
"""
import asyncio
import json
import os
import sys
from datetime import datetime

from app.services.gemini_extractor import GeminiExtractor
from app.services.untappd_searcher import get_untappd_url, scrape_beer_details
from app.services.brewery_manager import BreweryManager

# app/services/enrichment.py -> app/services -> app -> root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_FILE = os.path.join(BASE_DIR, "data", "beers.json")
OUTPUT_FILE = INPUT_FILE


async def process_beer_sequential(beer, index, total, extractor, brewery_manager):
    """Process a single beer sequentially"""
    print(f"\n{'='*70}")
    print(f"[{index}/{total}] Processing: {beer.get('name', 'Unknown')[:60]}")
    print(f"{'='*70}")
    
    # Step 1: Gemini Processing
    print("\n🤖 Step 1: Gemini Extraction")
    print("-" * 70)
    
    has_gemini_data = (
        beer.get('brewery_name_en') or beer.get('brewery_name_jp') or
        beer.get('beer_name_en') or beer.get('beer_name_jp')
    )
    
    if has_gemini_data:
        print(f"  ✅ Already has Gemini data - skipping")
        print(f"     Brewery: {beer.get('brewery_name_en', 'N/A')} / {beer.get('brewery_name_jp', 'N/A')}")
        print(f"     Beer: {beer.get('beer_name_en', 'N/A')} / {beer.get('beer_name_jp', 'N/A')}")
    else:
        known_brewery = None
        brewery_match = brewery_manager.find_brewery_in_text(beer['name'])
        if brewery_match:
            known_brewery = brewery_match.get('name_en')
            print(f"  🏭 Found known brewery hint: {known_brewery}")
        
        try:
            print(f"  🔄 Calling Gemini API...")
            enriched_info = await extractor.extract_info(beer['name'], known_brewery=known_brewery)
            
            if enriched_info:
                if enriched_info.get('brewery_name_jp'):
                    beer['brewery_name_jp'] = enriched_info['brewery_name_jp']
                if enriched_info.get('brewery_name_en'):
                    beer['brewery_name_en'] = enriched_info['brewery_name_en']
                if enriched_info.get('beer_name_jp'):
                    beer['beer_name_jp'] = enriched_info['beer_name_jp']
                if enriched_info.get('beer_name_en'):
                    beer['beer_name_en'] = enriched_info['beer_name_en']
                
                print(f"  ✅ Gemini extraction successful")
                print(f"     Brewery: {beer.get('brewery_name_en', 'N/A')} / {beer.get('brewery_name_jp', 'N/A')}")
                print(f"     Beer: {beer.get('beer_name_en', 'N/A')} / {beer.get('beer_name_jp', 'N/A')}")
            else:
                print(f"  ⚠️  Gemini returned no data")
        except Exception as e:
            print(f"  ❌ Gemini error: {e}")
    
    # Step 2: Untappd Processing
    print("\n🍺 Step 2: Untappd Enrichment")
    print("-" * 70)
    
    has_gemini_data = (
        beer.get('brewery_name_en') or beer.get('brewery_name_jp') or
        beer.get('beer_name_en') or beer.get('beer_name_jp')
    )
    
    if not has_gemini_data:
        print(f"  ⚠️  No Gemini data - skipping Untappd")
    else:
        if beer.get('untappd_url'):
            print(f"  ✅ Already has Untappd URL: {beer.get('untappd_url')}")
        else:
            brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
            beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
            
            try:
                print(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
                untappd_url = get_untappd_url(brewery, beer_name)
                
                if untappd_url:
                    beer['untappd_url'] = untappd_url
                    print(f"  ✅ Found Untappd URL: {untappd_url}")
                    
                    if "untappd.com/b/" in untappd_url:
                        await asyncio.sleep(2)  # Rate limit
                        print(f"  🔄 Scraping beer details...")
                        details = scrape_beer_details(untappd_url)
                        if details:
                            beer.update(details)
                            print(f"  ✅ Details scraped successfully")
                            print(f"     Style: {details.get('untappd_style', 'N/A')}")
                            print(f"     ABV: {details.get('untappd_abv', 'N/A')}, IBU: {details.get('untappd_ibu', 'N/A')}")
                            print(f"     Rating: {details.get('untappd_rating', 'N/A')} ({details.get('untappd_rating_count', 'N/A')})")
                        else:
                            print(f"  ⚠️  Could not scrape details")
                else:
                    print(f"  ❌ Untappd URL not found")
                
                await asyncio.sleep(1)  # Rate limit
            except Exception as e:
                print(f"  ❌ Untappd error: {e}")
    
    # Step 3: Brewery Database Update
    print("\n🏭 Step 3: Brewery Database Update")
    print("-" * 70)
    
    if beer.get('untappd_brewery_name'):
        before_count = len(brewery_manager.breweries)
        new_breweries = brewery_manager.extract_breweries_from_beers([beer])
        
        if new_breweries > 0:
            print(f"  ✅ Added new brewery: {beer.get('untappd_brewery_name')}")
            brewery_manager.save_breweries()
            print(f"  💾 Brewery database saved ({before_count} → {len(brewery_manager.breweries)} breweries)")
        else:
            print(f"  ℹ️  Brewery already in database: {beer.get('untappd_brewery_name')}")
    else:
        print(f"  ⚠️  No Untappd brewery name to add")
    
    return beer


async def sequential_enrichment(limit: int = 50):
    """Execute sequential enrichment"""
    print("=" * 70)
    print("🔄 Sequential Beer Enrichment (Gemini → Untappd → Brewery DB)")
    print("=" * 70)
    print(f"Target: First {limit} beers")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(INPUT_FILE):
        print(f"\n❌ Error: {INPUT_FILE} not found")
        print("💡 Run 'python -m app.cli scrape' first")
        return
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        beers = json.load(f)
    
    print(f"\n📂 Loaded {len(beers)} beers from database")
    
    to_process = beers[:limit]
    print(f"🎯 Processing first {len(to_process)} beers")
    
    extractor = GeminiExtractor()
    if not extractor.client:
        print("\n❌ Error: Gemini API key not configured")
        print("💡 Set GEMINI_API_KEY in .env file")
        return
    
    brewery_manager = BreweryManager()
    stats = brewery_manager.get_brewery_stats()
    print(f"\n🏭 Initial brewery database: {stats['total_breweries']} breweries")
    
    print(f"\n{'='*70}")
    print("🚀 Starting sequential processing...")
    print(f"{'='*70}")
    
    processed_count = 0
    gemini_enriched = 0
    untappd_enriched = 0
    breweries_added = 0
    
    initial_brewery_count = len(brewery_manager.breweries)
    
    for i, beer in enumerate(to_process, 1):
        try:
            had_gemini = bool(beer.get('brewery_name_en') or beer.get('brewery_name_jp'))
            had_untappd = bool(beer.get('untappd_url'))
            
            await process_beer_sequential(beer, i, len(to_process), extractor, brewery_manager)
            
            has_gemini = bool(beer.get('brewery_name_en') or beer.get('brewery_name_jp'))
            has_untappd = bool(beer.get('untappd_url'))
            
            if not had_gemini and has_gemini:
                gemini_enriched += 1
            if not had_untappd and has_untappd:
                untappd_enriched += 1
            
            processed_count += 1
            
            if i % 10 == 0:
                print(f"\n💾 Intermediate save (processed {i}/{len(to_process)})...")
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(beers, f, indent=4, ensure_ascii=False)
                print(f"  ✅ Saved to {OUTPUT_FILE}")
        
        except Exception as e:
            print(f"\n❌ Error processing beer {i}: {e}")
            continue
    
    breweries_added = len(brewery_manager.breweries) - initial_brewery_count
    
    print(f"\n{'='*70}")
    print("💾 Final save...")
    print(f"{'='*70}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(beers, f, indent=4, ensure_ascii=False)
    print(f"✅ Saved to {OUTPUT_FILE}")
    
    final_stats = brewery_manager.get_brewery_stats()
    
    print(f"\n{'='*70}")
    print("📈 Final Statistics")
    print(f"{'='*70}")
    print(f"  Beers processed: {processed_count}/{len(to_process)}")
    print(f"  Gemini enriched: {gemini_enriched}")
    print(f"  Untappd enriched: {untappd_enriched}")
    print(f"  Breweries added: {breweries_added}")
    print(f"  Total breweries: {final_stats['total_breweries']}")
    print(f"  Total beers in DB: {len(beers)}")
    print(f"\n  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'='*70}")
    print("✨ Sequential enrichment completed!")
    print(f"{'='*70}")

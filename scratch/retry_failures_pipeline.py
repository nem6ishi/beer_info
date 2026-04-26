import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client
from backend.src.services.gemini.extractor import GeminiExtractor
from backend.src.commands.enrich_untappd import process_beer_missing
from backend.src.services.store.brewery_manager import BreweryManager

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def retry_failures():
    supabase = get_supabase_client()
    
    # 1. Get failures
    res = supabase.table('untappd_search_failures').select('product_url').eq('resolved', False).execute()
    urls = [f['product_url'] for f in res.data]
    
    if not urls:
        print("No failures to retry.")
        return
        
    print(f"Found {len(urls)} failures to retry.")
    
    # 2. Setup services
    extractor = GeminiExtractor()
    brewery_manager = BreweryManager()
    
    # 3. Process each URL
    # We will chunk the db fetches
    url_chunks = [urls[i:i+50] for i in range(0, len(urls), 50)]
    
    total_processed = 0
    total_success = 0
    
    for chunk in url_chunks:
        # Get raw data for gemini extraction
        beers_res = supabase.table('beer_info_view').select('*').in_('url', chunk).execute()
        beers = beers_res.data
        
        for beer in beers:
            total_processed += 1
            url = beer['url']
            name = beer['name']
            shop = beer['shop']
            
            print(f"\n[{total_processed}/{len(urls)}] Processing: {name}")
            
            # Step A: Re-run Gemini Extraction
            try:
                gemini_res = await extractor.extract_info(name, shop)
                if gemini_res:
                    # Update gemini_data so beer dictionary has the latest names
                    gemini_updates = {
                        'brewery_name_jp': gemini_res.get('brewery_name_jp'),
                        'brewery_name_en': gemini_res.get('brewery_name_en'),
                        'beer_name_jp': gemini_res.get('beer_name_jp'),
                        'beer_name_en': gemini_res.get('beer_name_en'),
                        'beer_name_core': gemini_res.get('beer_name_core'),
                        'search_hint': gemini_res.get('search_hint'),
                        'product_type': gemini_res.get('product_type', 'beer'),
                        'is_set': gemini_res.get('is_set', False)
                    }
                    supabase.table('gemini_data').update(gemini_updates).eq('url', url).execute()
                    
                    # Update the beer dictionary with the new values so process_beer_missing uses them
                    for k, v in gemini_updates.items():
                        if v is not None:
                            beer[k] = v
            except Exception as e:
                print(f"  Gemini extraction failed: {e}")
            
            # Step B: Run Untappd Enrichment
            try:
                # Need to update search_attempts so process_beer_missing doesn't skip it?
                # Actually process_beer_missing doesn't check backoff, enrich_untappd does.
                result = await process_beer_missing(beer, brewery_manager=brewery_manager, extractor=extractor)
                if result:
                    print(f"  ✅ Success: {result.get('untappd_url')}")
                    total_success += 1
                else:
                    print(f"  ❌ Failed to find untappd url.")
            except Exception as e:
                print(f"  Error in untappd enrichment: {e}")
                
            await asyncio.sleep(1) # rate limit

    print(f"\nDone! Processed: {total_processed}, Success: {total_success}")

if __name__ == "__main__":
    asyncio.run(retry_failures())

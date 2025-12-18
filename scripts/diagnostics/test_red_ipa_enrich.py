import sys
import os
import asyncio

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.enrich_untappd import process_beer_missing
from scripts.utils.script_utils import setup_script

async def test_re_enrich():
    supabase, logger = setup_script("test_re_enrich")
    
    # Target: West Coast Brewing / Red IPA
    target_name = "ウエストコーストブルーイング / レッド IPA 510ml缶 [West Coast Brewing / Red IPA]"
    
    # Fetch from DB
    res = supabase.table('scraped_beers').select('*').eq('name', target_name).execute()
    if not res.data:
        print("Product not found.")
        return

    beer = res.data[0]
    print(f"Testing re-enrichment for: {beer['name']}")
    print(f"Current Untappd URL: {beer.get('untappd_url')}")
    
    # Force re-enrichment by clearing untappd_url for the test call (local only, not in DB)
    test_beer = beer.copy()
    test_beer['untappd_url'] = None
    
    # Run process_beer_missing
    result = await process_beer_missing(supabase, test_beer, offline=False)
    
    if result:
        print(f"SUCCESS! Result: {result}")
    else:
        print("FAILED to enrich.")

if __name__ == '__main__':
    asyncio.run(test_re_enrich())

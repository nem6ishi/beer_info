
import asyncio
import os
import sys
import logging
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.enrich_untappd import process_beer_missing
from scripts.utils.script_utils import setup_script

# Setup
supabase, logger = setup_script("fix_obercreek")

async def fix_obercreek():
    # 1. Fetch the target items
    res = supabase.table('beer_info_view').select('*').ilike('name', '%Obercreek Found Dead%').execute()
    beers = res.data
    
    print(f"Found {len(beers)} items to fix.")
    
    for beer in beers:
        print(f"Processing: {beer['name']}")
        
        # 2. Clear stale URL in DB (gemini_data persistence)
        if beer.get('url'):
            supabase.table('gemini_data').update({'untappd_url': None}).eq('url', beer['url']).execute()
            print("  Cleared gemini_data.untappd_url")
            beer['untappd_url'] = None
        
        # 3. Re-process
        print(f"  Using Brewery: {beer.get('brewery_name_en')}")
        print(f"  Using Beer: {beer.get('beer_name_en')}")
        
        await process_beer_missing(beer, supabase)
        print("  Done.")

if __name__ == "__main__":
    asyncio.run(fix_obercreek())

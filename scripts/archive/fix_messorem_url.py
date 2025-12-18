
import asyncio
import os
import sys
import logging
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.enrich_untappd import process_beer_missing
from scripts.utils.script_utils import setup_script

# Setup
supabase, logger = setup_script("fix_messorem")

async def fix_messorem():
    # 1. Fetch the target items
    res = supabase.table('beer_info_view').select('*').ilike('name', '%MESSOREM Triple Tombe%').execute()
    beers = res.data
    
    print(f"Found {len(beers)} items to fix.")
    
    for beer in beers:
        print(f"Processing: {beer['name']}")
        
        # 2. Clear stale URL in DB (gemini_data persistence)
        # We need to clear it so process_beer_missing searches again
        if beer.get('url'):
            supabase.table('gemini_data').update({'untappd_url': None}).eq('url', beer['url']).execute()
            print("  Cleared gemini_data.untappd_url")
            # Also clear from beer object for the function call
            beer['untappd_url'] = None
        
        # 3. Re-process
        # Ensure we have the CORRECT names from the view (which we do, as we just fetched)
        # But wait, did beer_info_view update? verify
        print(f"  Using Brewery: {beer.get('brewery_name_en')}") # Should be MESSOREM
        print(f"  Using Beer: {beer.get('beer_name_en')}")       # Should be Triple Tombe
        
        await process_beer_missing(beer, supabase)
        print("  Done.")

if __name__ == "__main__":
    asyncio.run(fix_messorem())

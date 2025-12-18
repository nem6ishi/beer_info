import os
import sys
import asyncio

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from scripts.utils.script_utils import setup_script
from scripts.enrich_breweries import enrich_breweries

async def fix_brewery():
    supabase, logger = setup_script("FixAndBeer")
    
    untappd_url = "https://untappd.com/b/and-beer-tamiru-tadesse-coffee-ale/6488346"
    correct_brewery_url = "https://untappd.com/w/and-beer/385368"
    correct_brewery_name = "And Beer"
    
    logger.info("Updating untappd_data...")
    
    # Update the record
    response = supabase.table('untappd_data').update({
        'untappd_brewery_url': correct_brewery_url,
        'brewery_name': correct_brewery_name
    }).eq('untappd_url', untappd_url).execute()
    
    if response.data:
        logger.info(f"Successfully updated record: {response.data[0].get('beer_name')}")
    else:
        logger.error("Failed to update record (or record not found).")
        return

    logger.info("Triggering brewery enrichment to fetch 'And Beer' details...")
    
    # Run enrichment specifically for this brewery (by running general enrichment, it should pick it up as new)
    # limit=5 should be enough to pick up the new one, force=False is fine as it's new
    await enrich_breweries(limit=5)
    
if __name__ == "__main__":
    asyncio.run(fix_brewery())

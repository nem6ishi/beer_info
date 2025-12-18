import asyncio
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.enrich_untappd import process_beer_missing
from scripts.utils.script_utils import setup_script

async def redo_enrichment(urls):
    supabase, logger = setup_script("redo_enrich")
    
    for url in urls:
        print(f"--- Redoing: {url} ---")
        # Fetch current record
        res = supabase.table('beer_info_view').select('*').eq('url', url).execute()
        if not res.data:
            print(f"URL not found in DB: {url}")
            continue
        
        beer = res.data[0]
        # Force re-lookup by setting untappd_url to None in the dict passed to process_beer_missing
        beer_to_process = beer.copy()
        beer_to_process['untappd_url'] = None
        
        result = await process_beer_missing(beer_to_process, supabase, offline=False)
        print(f"Result for {url}: {result}")

if __name__ == '__main__':
    target_urls = [
        "https://www.arome.jp/products/detail.php?product_id=6559",
        "https://151l.shop/?pid=189829231"
    ]
    asyncio.run(redo_enrichment(target_urls))

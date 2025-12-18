import asyncio
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.enrich_untappd import process_beer_missing
from scripts.utils.script_utils import setup_script

async def fix_reported_items():
    supabase, logger = setup_script("fix_reported")
    
    # 1. Manual fix for Craftrock Joyhopozits
    joyhop_url = "https://151l.shop/?pid=189829231"
    joyhop_untappd = "https://untappd.com/b/craftrock-brewing-joy-hopposites/3435960"
    
    # Update gemini_data and scraped_beers
    supabase.table('gemini_data').update({'untappd_url': joyhop_untappd}).eq('url', joyhop_url).execute()
    supabase.table('scraped_beers').update({'untappd_url': joyhop_untappd}).eq('url', joyhop_url).execute()
    print(f"Manually fixed Joy Hopposites: {joyhop_url}")

    # 2. Re-enrich items with search-result URLs or missing URLs for reported breweries
    # Find all items from 'Arôme' or '一期一会～る' with search results or None
    res = supabase.table('scraped_beers').select('*').or_('untappd_url.is.null,untappd_url.ilike.%/search?%').execute()
    
    target_names = ["Red IPA", "Imperial Red IPA", "Joyhopozits"]
    
    to_redo = []
    for item in res.data:
        name = item.get('name', '')
        if any(keyword.lower() in name.lower() for keyword in target_names):
            to_redo.append(item)
    
    print(f"Found {len(to_redo)} items to re-enrich.")
    
    for item in to_redo:
        print(f"Redoing: {item['name']} ({item['url']})")
        # Need to fetch full data (including Gemini fields) for process_beer_missing
        full_res = supabase.table('beer_info_view').select('*').eq('url', item['url']).execute()
        if not full_res.data:
            continue
        
        beer = full_res.data[0]
        # Clear persistent search URL if any (already handled by improved enrichment logic in enrich_untappd.py)
        # but for safety let's pass it with None
        beer_to_process = beer.copy()
        beer_to_process['untappd_url'] = None
        
        result = await process_beer_missing(beer_to_process, supabase, offline=False)
        print(f"Result: {result}")

if __name__ == '__main__':
    asyncio.run(fix_reported_items())

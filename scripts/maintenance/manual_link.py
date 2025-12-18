import os
import sys
import argparse
import asyncio
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.utils.script_utils import setup_script
from app.services.untappd_searcher import scrape_beer_details
from scripts.enrich_untappd import map_details_to_payload

async def manual_link(product_url, untappd_url):
    supabase, logger = setup_script("ManualLink")
    
    logger.info(f"Linking {product_url} -> {untappd_url}")
    
    # 1. Scrape Untappd details
    logger.info("Scraping details...")
    untappd_payload = {}
    details = scrape_beer_details(untappd_url)
    if details:
        untappd_payload = map_details_to_payload(details)
        untappd_payload['untappd_url'] = untappd_url
        logger.info(f"Details scraped: {details.get('untappd_beer_name')}")
    else:
        logger.warning(f"Could not scrape details for {untappd_url}")
        untappd_payload = {
            'untappd_url': untappd_url,
            'fetched_at': datetime.now(timezone.utc).isoformat()
        }

    # 2. Upsert untappd_data
    try:
        supabase.table('untappd_data').upsert(untappd_payload).execute()
        logger.info("Saved to untappd_data")
    except Exception as e:
        logger.error(f"Error saving to untappd_data: {e}")

    # 3. Update gemini_data
    try:
        supabase.table('gemini_data').update({'untappd_url': untappd_url}).eq('url', product_url).execute()
        logger.info("Updated gemini_data")
    except Exception as e:
        logger.error(f"Error updating gemini_data: {e}")

    # 4. Update scraped_beers
    try:
        supabase.table('scraped_beers').update({'untappd_url': untappd_url}).eq('url', product_url).execute()
        logger.info("Updated scraped_beers")
    except Exception as e:
        logger.warning(f"Error updating scraped_beers: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('product_url', type=str, help='Product Page URL')
    parser.add_argument('untappd_url', type=str, help='Untappd URL')
    args = parser.parse_args()
    
    asyncio.run(manual_link(args.product_url, args.untappd_url))

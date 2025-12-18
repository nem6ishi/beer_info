import os
import sys
import asyncio
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import scrape_beer_details, scrape_brewery_details
from scripts.utils.script_utils import setup_script

async def fix_leffe():
    supabase, logger = setup_script("FixLeffe")
    
    target_url = "https://untappd.com/b/abbaye-de-leffe-leffe-brune-bruin/5940"
    logger.info(f"Refetching data for: {target_url}")
    
    # 1. Scrape Beer Details (using updated scraper)
    details = scrape_beer_details(target_url)
    
    if not details or not details.get('untappd_brewery_name'):
        logger.error("Failed to scrape details or missing brewery name.")
        return

    brewery_name = details.get('untappd_brewery_name')
    brewery_url = details.get('untappd_brewery_url')
    
    logger.info(f"Scraped Brewery Name: '{brewery_name}'")
    logger.info(f"Scraped Brewery URL:  '{brewery_url}'")
    
    if "Subsidiary" in brewery_name:
        logger.error("❌ Scraper still returning 'Subsidiary'! Fix scraper first.")
        return

    # 2. Update untappd_data
    payload = {
        'untappd_url': target_url,  # Primary Key Required!
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': brewery_name,
        'untappd_brewery_url': brewery_url,
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'ibu': details.get('untappd_ibu'),
        'rating': details.get('untappd_rating'),
        'rating_count': details.get('untappd_rating_count'),
        'image_url': details.get('untappd_label'),
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }
    
    res = supabase.table('untappd_data').upsert(payload, on_conflict='untappd_url').execute()
    logger.info(f"✅ untappd_data updated. Status: {res}")
    
    # 3. Enrich Brewery (if URL exists)
    if brewery_url:
        logger.info(f"Enriching brewery: {brewery_url}")
        b_details = scrape_brewery_details(brewery_url)
        
        if b_details:
            b_payload = {
                'untappd_url': brewery_url,
                'name_en': b_details.get('brewery_name'),
                'location': b_details.get('location'),
                'brewery_type': b_details.get('brewery_type'),
                'website': b_details.get('website'),
                'logo_url': b_details.get('logo_url'),
                'stats': b_details.get('stats'),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            supabase.table('breweries').upsert(b_payload, on_conflict='untappd_url').execute()
            logger.info(f"✅ Breweries table updated for: {b_details.get('brewery_name')}")

if __name__ == "__main__":
    asyncio.run(fix_leffe())

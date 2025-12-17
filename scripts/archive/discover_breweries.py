import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.untappd_searcher import search_brewery, scrape_brewery_details

# Configure Logging
from scripts.utils.script_utils import setup_script

# Setup Supabase and Logging
supabase, logger = setup_script("discover")

async def discover_and_enrich():
    # 1. Find brewery names that are missing URLs
    # We want distinct brewery names from untappd_data where untappd_brewery_url is null
    # Supabase doesn't do DISTINCT easily. We fetch all and dedupe in python.
    
    logger.info("Fetching brewery names from untappd_data...")
    res = supabase.table('untappd_data').select('brewery_name').is_('untappd_brewery_url', 'null').execute()
    
    all_names = [r['brewery_name'] for r in res.data if r.get('brewery_name')]
    unique_missing = sorted(list(set(all_names)))
    
    logger.info(f"Found {len(unique_missing)} unique brewery names with missing URLs.")
    
    for i, name in enumerate(unique_missing):
        logger.info(f"[{i+1}/{len(unique_missing)}] Searching for: {name}")
        
        # Search
        url = search_brewery(name)
        await asyncio.sleep(2) # Rate limit
        
        if url:
            logger.info(f"  ✅ Found URL: {url}")
            
            # 1. Scrape details immediately to populate 'breweries' table
            details = scrape_brewery_details(url)
            await asyncio.sleep(2) # Rate limit
            
            if details:
                payload = {
                    'untappd_url': url,
                    'name_en': details.get('brewery_name'),
                    'location': details.get('location'),
                    'brewery_type': details.get('brewery_type'),
                    'website': details.get('website'),
                    'logo_url': details.get('logo_url'),
                    'stats': details.get('stats'),
                    'updated_at': details.get('fetched_at') or 'now()'
                }
                if not details or not details.get('brewery_name'):
                     logger.warning("  ⚠️  Scraped details missing brewery name. Skipping.")
                     continue

                try:
                    name_en = details.get('brewery_name')
                    # Check if name exists to avoid unique constraint violation
                    # Use execute() instead of maybe_single() to avoid 406 Not Acceptable
                    res_existing = supabase.table('breweries').select('id').eq('name_en', name_en).execute()
                    
                    if res_existing.data and len(res_existing.data) > 0:
                         # Update existing record
                         bid = res_existing.data[0]['id']
                         supabase.table('breweries').update(payload).eq('id', bid).execute()
                         logger.info(f"  💾 Updated existing brewery '{details.get('brewery_name')}' (ID: {bid})")
                    else:
                        # Insert new
                        supabase.table('breweries').upsert(payload, on_conflict='untappd_url').execute()
                        logger.info("  💾 Saved new brewery to table.")
                    
                    # 2. Backfill untappd_data
                    supabase.table('untappd_data').update({'untappd_brewery_url': url}) \
                        .eq('brewery_name', name) \
                        .execute()
                    logger.info("  🔗 Linked in 'untappd_data'.")
                    
                except Exception as e:
                    logger.error(f"  ❌ Database error: {e}")
            else:
                 logger.warning("  ⚠️  Found URL but failed to scrape details.")
        else:
            logger.warning(f"  ❌ Not found on Untappd.")

if __name__ == "__main__":
    asyncio.run(discover_and_enrich())

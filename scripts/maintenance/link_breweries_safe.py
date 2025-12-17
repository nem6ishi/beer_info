#!/usr/bin/env python3
"""
Maintenance Script: Link Breweries Safe
Backfills `untappd_brewery_url` in `untappd_data` by scraping the beer page directly.
This replaces the unsafe 'guess by search' method.
"""
import asyncio
import os
import sys
import logging
from datetime import datetime
from supabase import create_client

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import scrape_beer_details, scrape_brewery_details
from scripts.utils.script_utils import setup_script

async def link_breweries_safe(limit: int = 50):
    supabase, logger = setup_script("LinkBreweriesSafe")
    
    logger.info("=" * 70)
    logger.info(f"🔗 Safe Brewery Linking (Limit: {limit})")
    logger.info("=" * 70)
    
    # 1. Find beers with Untappd URL but missing Brewery URL
    # We want rows where untappd_url IS NOT NULL AND untappd_brewery_url IS NULL
    res = supabase.table('untappd_data') \
        .select('untappd_url, beer_name') \
        .like('untappd_url', '%/b/%') \
        .is_('untappd_brewery_url', 'null') \
        .limit(limit) \
        .execute()
        
    targets = res.data
    logger.info(f"Found {len(targets)} beers needing brewery links.")
    
    if not targets:
        return

    processed = 0
    
    for i, beer in enumerate(targets, 1):
        url = beer.get('untappd_url')
        name = beer.get('beer_name')
        
        logger.info(f"\n[{i}/{len(targets)}] Processing: {name}")
        logger.info(f"  🔗 Beer URL: {url}")
        
        if not url or "untappd.com/b/" not in url:
            logger.warning("  ⚠️  Invalid URL. Skipping.")
            continue
            
        try:
            # Scrape beer page
            await asyncio.sleep(2)
            details = scrape_beer_details(url)
            
            brewery_url = details.get('untappd_brewery_url')
            brewery_name = details.get('untappd_brewery_name')
            
            if brewery_url and "untappd.com" in brewery_url:
                logger.info(f"  ✅ Found Brewery: {brewery_name} ({brewery_url})")
                
                # Update untappd_data
                supabase.table('untappd_data').update({
                    'untappd_brewery_url': brewery_url,
                    'brewery_name': brewery_name # Update name too just in case
                }).eq('untappd_url', url).execute()
                
                # Check if we need to enrich the brewery itself
                # (Optional, but good to ensure the brewery exists in 'breweries' table)
                b_check = supabase.table('breweries').select('id').eq('untappd_url', brewery_url).maybe_single().execute()
                
                if not b_check.data:
                    logger.info(f"  🏭 Brewery not in DB. Enriching now...")
                    await asyncio.sleep(2)
                    b_details = scrape_brewery_details(brewery_url)
                    
                    if b_details:
                        payload = {
                            'untappd_url': brewery_url,
                            'name_en': b_details.get('brewery_name'),
                            'location': b_details.get('location'),
                            'brewery_type': b_details.get('brewery_type'),
                            'website': b_details.get('website'),
                            'logo_url': b_details.get('logo_url'),
                            'stats': b_details.get('stats'),
                            'updated_at': datetime.now().isoformat()
                        }
                        supabase.table('breweries').upsert(payload, on_conflict='untappd_url').execute()
                        logger.info("  💾 Brewery saved.")
                    else:
                        logger.warning("  ⚠️  Failed to scrape brewery details.")
                
                processed += 1
            else:
                logger.warning("  ⚠️  Could not extract brewery URL from page.")
                
        except Exception as e:
            logger.error(f"  ❌ Error processing {url}: {e}")
            
    logger.info(f"\nDone. Processed {processed} beers.")

if __name__ == "__main__":
    asyncio.run(link_breweries_safe(limit=50))

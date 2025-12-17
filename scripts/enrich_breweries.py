#!/usr/bin/env python3
"""
Brewery Enrichment Script (Untappd)
Enriches the `breweries` table with details from Untappd (Location, Type, Stats, etc.)

Strategy:
1. Scan `untappd_data` for distinct `untappd_brewery_url`.
2. For each URL:
    a. Check if already enriched in `breweries` table (and fresh enough).
    b. If not, scrape details using `untappd_searcher.scrape_brewery_details`.
    c. Upsert into `breweries`.
"""
import asyncio
import os
import sys
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from dateutil import parser
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import scrape_brewery_details, UntappdBreweryDetails

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("enrich_breweries")

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

# Get credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)


async def enrich_breweries(limit: int = 50, force: bool = False, target_urls: list = None):
    logger.info("=" * 70)
    logger.info(f"🏭 Brewery Enrichment (Limit: {limit}, Force: {force})")
    if target_urls:
         logger.info(f"🎯 Target: {len(target_urls)} specific breweries")
    logger.info("=" * 70)
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Get distinct brewery URLs from untappd_data
    unique_urls = []
    
    if target_urls:
        unique_urls = list(set(target_urls))
        logger.info(f"  🎯 Processing {len(unique_urls)} provided brewery URLs...")
    else:
        logger.info("  🔍 Collecting unique brewery URLs from beer data...")
        # Paginate if needed, but for now grab distinct
        # Supabase doesn't support distinct easily on select without rpc, so we fetch and set
        res = supabase.table('untappd_data').select('untappd_brewery_url, brewery_name').not_.is_('untappd_brewery_url', 'null').execute()
        
        # Simple list of URLs
        data = res.data
        if not data:
            logger.info("  ✨ No brewery URLs found in untappd_data.")
            return

        unique_urls = list(set([item['untappd_brewery_url'] for item in data if item.get('untappd_brewery_url')]))
        logger.info(f"  found {len(unique_urls)} unique brewery URLs.")
    
    total_processed = 0
    
    for url in unique_urls:
        if total_processed >= limit:
            break
            
        # Check if exists in breweries table
        existing = supabase.table('breweries').select('*').eq('untappd_url', url).execute()
        
        should_process = False
        
        if not existing.data:
            should_process = True
        else:
            if force:
                should_process = True
            else:
                 # Check freshness
                updated_at = existing.data[0].get('updated_at')
                if updated_at:
                    try:
                        last_update = parser.parse(updated_at)
                    except NameError:
                        from dateutil import parser
                        last_update = parser.parse(updated_at)
                        
                    if datetime.now(timezone.utc) - last_update < timedelta(days=7):
                        continue
                else:
                    should_process = True
        
        if should_process:
            logger.info(f"  🔄 Enriching: {url}")
            await asyncio.sleep(2) # Rate limit
            details = scrape_brewery_details(url)
            
            if details:
                payload = {
                     'untappd_url': url,
                     'name_en': details.get('brewery_name'),
                     'location': details.get('location'),
                     'brewery_type': details.get('brewery_type'),
                     'website': details.get('website'),
                     'logo_url': details.get('logo_url'),
                     'stats': details.get('stats'),
                     'updated_at': datetime.now(timezone.utc).isoformat()
                }
                
                try:
                    supabase.table('breweries').upsert(payload, on_conflict='untappd_url').execute()
                    logger.info(f"  ✅ Saved: {details.get('brewery_name')}")
                    total_processed += 1
                except Exception as e:
                    logger.error(f"  ❌ Error saving: {e}")
            else:
                logger.warning(f"  ⚠️ Failed to scrape: {url}")
        else:
            pass

    logger.info(f"\n✨ Brewery enrichment completed. Processed {total_processed} breweries.")

if __name__ == "__main__":
    import argparse
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--limit', type=int, default=50)
    arg_parser.add_argument('--force', action='store_true', help="Force update even if fresh")
    args = arg_parser.parse_args()
    
    asyncio.run(enrich_breweries(limit=args.limit, force=args.force))

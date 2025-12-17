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


async def enrich_breweries(limit: int = 50, force: bool = False):
    logger.info("=" * 70)
    logger.info(f"🏭 Brewery Enrichment (Limit: {limit}, Force: {force})")
    logger.info("=" * 70)
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Get distinct brewery URLs from untappd_data
    # Note: .select('untappd_brewery_url', count='exact').not_.is_('untappd_brewery_url', 'null') doesn't distinct easily in API without RPC?
    # Actually Supabase JS/Py client supports modifiers but distinct is tricky. 
    # Use RPC if available, or just fetch all (cached?) or efficient query.
    # We'll fetch all unique non-null brewery URLs.
    # Since we don't have a distinct helper easily, we page through or just get all (assuming not millions).
    
    logger.info("  🔍 Collecting unique brewery URLs from beer data...")
    
    # Simple pagination to get distinct URLs locally (inefficient for large datasets but fine for <10k beers)
    # Ideally should create a view or RPC: `SELECT DISTINCT untappd_brewery_url FROM untappd_data WHERE ...`
    
    # Let's try to search specifically for ones we haven't processed.
    # For now, fetching all brewery URLs from untappd_data is okay if dataset is small.
    
    res = supabase.table('untappd_data').select('untappd_brewery_url, brewery_name').not_.is_('untappd_brewery_url', 'null').execute()
    
    if not res.data:
        logger.info("  ⚠️  No brewery URLs found in untappd_data. Have you enriched beers with brewery links yet?")
        return

    # Map URL to Name (for logging)
    url_to_name = {item['untappd_brewery_url']: item['brewery_name'] for item in res.data}
    unique_urls = list(url_to_name.keys())
    
    logger.info(f"  found {len(unique_urls)} unique brewery URLs.")
    
    processed_count = 0
    
    for url in unique_urls:
        if processed_count >= limit:
            break
            
        brewery_name = url_to_name[url]
        
        # Check if exists in breweries table and is fresh
        existing = supabase.table('breweries').select('*').eq('untappd_url', url).execute()
        
        if existing.data and not force:
            # Check freshness
            updated_at = existing.data[0].get('updated_at')
            if updated_at:
                last_update = parser.parse(updated_at)
                if datetime.now(timezone.utc) - last_update < timedelta(days=7):
                    # Skip if updated recently
                    # logger.info(f"  ⏭️  Skipping {brewery_name} (Updated recently)")
                    continue

        logger.info(f"\n🏭 Processing [{processed_count + 1}/{limit}]: {brewery_name}")
        logger.info(f"  🔗 {url}")
        
        try:
            # Scrape
            await asyncio.sleep(2) # Rate limit
            details = scrape_brewery_details(url)
            
            if details:
                # Prepare payload
                payload = {
                    'untappd_url': url,
                    'name_en': details.get('brewery_name'), # Assuming EN scraper
                    'location': details.get('location'),
                    'brewery_type': details.get('brewery_type'),
                    'website': details.get('website'),
                    'logo_url': details.get('logo_url'),
                    'stats': details.get('stats'),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
                
                # Upsert based on untappd_url
                # Note: 'breweries' table primary key is UUID, but we have UNIQUE constraint on untappd_url (hopefully added in schema)
                # We need to perform Upsert on untappd_url. Supabase-py upsert usually requires matching primary key or specified constraints.
                # If we rely on untappd_url being UNIQUE, we can use on_conflict.
                
                res = supabase.table('breweries').upsert(payload, on_conflict='untappd_url').execute()
                logger.info(f"  ✅ Enriched: {details.get('brewery_name')}")
                processed_count += 1
            else:
                logger.warning("  ⚠️  Failed to scrape details")
                
        except Exception as e:
            logger.error(f"  ❌ Error processing {brewery_name}: {e}")

    logger.info(f"\n✨ Brewery enrichment completed. Processed {processed_count} breweries.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--force', action='store_true', help="Force update even if fresh")
    args = parser.parse_args()
    
    asyncio.run(enrich_breweries(limit=args.limit, force=args.force))

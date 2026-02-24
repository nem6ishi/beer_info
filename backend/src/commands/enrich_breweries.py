"""
Brewery Enrichment Script (Untappd)
Enriches the `breweries` table with details from Untappd.
Optimized to reduce N+1 queries by caching existing records.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from dateutil import parser

from backend.src.core.db import get_supabase_client
from backend.src.services.untappd.searcher import scrape_brewery_details

logger = logging.getLogger(__name__)

async def enrich_breweries(limit: int = 50, force: bool = False, target_urls: list = None):
    logger.info("=" * 70)
    logger.info(f"🏭 Brewery Enrichment (Limit: {limit}, Force: {force})")
    if target_urls:
         logger.info(f"🎯 Target: {len(target_urls)} specific breweries")
    logger.info("=" * 70)
    
    supabase = get_supabase_client()
    
    # Cache existing breweries
    logger.info("  🔍 Caching existing breweries from DB...")
    all_breweries_res = supabase.table('breweries').select('id, untappd_url, name_en, updated_at').execute()
    
    breweries_by_url = {b['untappd_url']: b for b in all_breweries_res.data if b.get('untappd_url')}
    breweries_by_name = {b['name_en']: b for b in all_breweries_res.data if b.get('name_en')}
    logger.info(f"    ✅ Cached {len(all_breweries_res.data)} breweries.")
    
    total_processed = 0
    processed_urls = set()
    
    # Helper to check freshness locally
    def should_process_url(url: str) -> bool:
        if force:
            return True
        existing = breweries_by_url.get(url)
        if not existing:
            return True
        updated_at = existing.get('updated_at')
        if not updated_at:
            return True
        try:
            last_update = parser.parse(updated_at)
            # If updated in the last 7 days, skip
            if datetime.now(timezone.utc) - last_update < timedelta(days=7):
                return False
        except Exception:
            return True
        return True

    # Common processing block
    async def process_single_brewery(url: str) -> bool:
        if url in processed_urls:
            return False
            
        if not should_process_url(url):
            logger.info(f"  ⏭️  Skipped (recently updated): {url}")
            processed_urls.add(url)
            return False
            
        logger.info(f"  🔄 Enriching: {url}")
        await asyncio.sleep(2) # Rate limit
        details = scrape_brewery_details(url)
        
        if not details:
            logger.warning(f"  ⚠️ Failed to scrape: {url}")
            processed_urls.add(url)
            return False
            
        brewery_name = details.get('brewery_name')
        
        # Check by name in cache
        target_id = None
        existing_by_name = breweries_by_name.get(brewery_name)
        
        if existing_by_name:
            existing_url = existing_by_name.get('untappd_url')
            # Same brewery but different URL (e.g., vanity URL vs /w/ URL)
            if existing_url and existing_url != url:
                logger.info(f"  ⏭️  Skipped: '{brewery_name}' already exists with different URL: {existing_url}")
                processed_urls.add(url)
                return False
            elif not existing_url:
                logger.info(f"  📝 Matching to existing record with null URL: {brewery_name}")
                target_id = existing_by_name['id']
            elif existing_url == url:
                target_id = existing_by_name['id']
                
        # If not found by name, try by URL just in case name changed
        if not target_id:
            existing_by_url = breweries_by_url.get(url)
            if existing_by_url:
                target_id = existing_by_url['id']
        
        payload = {
             'untappd_url': url,
             'name_en': brewery_name,
             'location': details.get('location'),
             'brewery_type': details.get('brewery_type'),
             'website': details.get('website'),
             'logo_url': details.get('logo_url'),
             'stats': details.get('stats'),
             'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            if target_id:
                # Update existing record
                supabase.table('breweries').update(payload).eq('id', target_id).execute()
                logger.info(f"  ✅ Updated: {brewery_name}")
            else:
                # Insert new record
                res = supabase.table('breweries').insert(payload).execute()
                if res.data:
                    # Add to cache for subsequent checks
                    new_rec = res.data[0]
                    breweries_by_url[url] = new_rec
                    breweries_by_name[brewery_name] = new_rec
                logger.info(f"  ✅ Inserted: {brewery_name}")
            
            processed_urls.add(url)
            return True
        except Exception as e:
            logger.error(f"  ❌ Error saving {url}: {e}")
            return False


    # PRIORITY 1: Process target_urls first (these don't count against limit)
    if target_urls:
        logger.info(f"\n🎯 PRIORITY: Processing {len(target_urls)} target breweries...")
        for url in target_urls:
            if await process_single_brewery(url):
                total_processed += 1
        logger.info(f"\n✅ Priority processing complete. Processed {total_processed} target breweries.")
    
    # PRIORITY 2: Process additional breweries from untappd_data (up to limit)
    if total_processed < limit:
        remaining_limit = limit - total_processed
        logger.info(f"\n📂 Processing additional breweries from database (up to {remaining_limit})...")
        
        # Get distinct brewery URLs from untappd_data
        logger.info("  🔍 Collecting unique brewery URLs from beer data...")
        res = supabase.table('untappd_data').select('untappd_brewery_url').not_.is_('untappd_brewery_url', 'null').limit(5000).execute()
        
        data = res.data
        if not data:
            logger.info("  ✨ No brewery URLs found in untappd_data.")
        else:
            unique_urls = list(set([item['untappd_brewery_url'] for item in data if item.get('untappd_brewery_url')]))
            logger.info(f"  Found {len(unique_urls)} unique brewery URLs.")
            
            for url in unique_urls:
                if total_processed >= limit:
                    break
                
                if await process_single_brewery(url):
                    total_processed += 1

    logger.info(f"\n✨ Brewery enrichment completed. Processed {total_processed} breweries.")

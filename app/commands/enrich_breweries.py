"""
Brewery Enrichment Script (Untappd)
Enriches the `breweries` table with details from Untappd.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from dateutil import parser

from app.core.db import get_supabase_client
from app.services.untappd.searcher import scrape_brewery_details

logger = logging.getLogger(__name__)

async def enrich_breweries(limit: int = 50, force: bool = False, target_urls: list = None):
    logger.info("=" * 70)
    logger.info(f"🏭 Brewery Enrichment (Limit: {limit}, Force: {force})")
    if target_urls:
         logger.info(f"🎯 Target: {len(target_urls)} specific breweries")
    logger.info("=" * 70)
    
    supabase = get_supabase_client()
    
    # 1. Get distinct brewery URLs from untappd_data
    unique_urls = []
    
    if target_urls:
        unique_urls = list(set(target_urls))
        logger.info(f"  🎯 Processing {len(unique_urls)} provided brewery URLs...")
    else:
        logger.info("  🔍 Collecting unique brewery URLs from beer data...")
        # Paginate if needed, but for now grab distinct
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
                        if datetime.now(timezone.utc) - last_update < timedelta(days=7):
                            continue
                    except:
                        should_process = True
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

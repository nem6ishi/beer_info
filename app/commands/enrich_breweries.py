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
    
    total_processed = 0
    processed_urls = set()
    
    # PRIORITY 1: Process target_urls first (these don't count against limit)
    if target_urls:
        logger.info(f"\n🎯 PRIORITY: Processing {len(target_urls)} target breweries...")
        
        for url in target_urls:
            if url in processed_urls:
                continue
            
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
                                logger.info(f"  ⏭️  Skipped (recently updated): {url}")
                                processed_urls.add(url)
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
                    brewery_name = details.get('brewery_name')
                    
                    # Additional check: Does a brewery with this name already exist?
                    name_check = supabase.table('breweries').select('*').eq('name_en', brewery_name).execute()
                    
                    if name_check.data and len(name_check.data) > 0:
                        existing_brewery = name_check.data[0]
                        existing_url = existing_brewery.get('untappd_url')
                        
                        # Same brewery but different URL (e.g., vanity URL vs /w/ URL)
                        if existing_url != url:
                            logger.info(f"  ⏭️  Skipped: '{brewery_name}' already exists with different URL: {existing_url}")
                            processed_urls.add(url)
                            continue
                    
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
                        # Check if record exists by untappd_url (primary unique key)
                        existing_res = supabase.table('breweries').select('id').eq('untappd_url', url).execute()
                        
                        if existing_res.data and len(existing_res.data) > 0:
                            # Update existing record
                            supabase.table('breweries').update(payload).eq('untappd_url', url).execute()
                            logger.info(f"  ✅ Updated: {brewery_name}")
                        else:
                            # Insert new record
                            supabase.table('breweries').insert(payload).execute()
                            logger.info(f"  ✅ Inserted: {brewery_name}")
                        
                        total_processed += 1
                        processed_urls.add(url)
                    except Exception as e:
                        logger.error(f"  ❌ Error saving {url}: {e}")
                else:
                    logger.warning(f"  ⚠️ Failed to scrape: {url}")
            else:
                processed_urls.add(url)
        
        logger.info(f"\n✅ Priority processing complete. Processed {total_processed} target breweries.")
    
    # PRIORITY 2: Process additional breweries from untappd_data (up to limit)
    if total_processed < limit:
        remaining_limit = limit - total_processed
        logger.info(f"\n📂 Processing additional breweries from database (up to {remaining_limit})...")
        
        # Get distinct brewery URLs from untappd_data
        logger.info("  🔍 Collecting unique brewery URLs from beer data...")
        res = supabase.table('untappd_data').select('untappd_brewery_url, brewery_name').not_.is_('untappd_brewery_url', 'null').limit(5000).execute()
        
        data = res.data
        if not data:
            logger.info("  ✨ No brewery URLs found in untappd_data.")
        else:
            unique_urls = list(set([item['untappd_brewery_url'] for item in data if item.get('untappd_brewery_url')]))
            logger.info(f"  Found {len(unique_urls)} unique brewery URLs.")
            
            for url in unique_urls:
                if total_processed >= limit:
                    break
                
                # Skip if already processed
                if url in processed_urls:
                    continue
                    
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
                        brewery_name = details.get('brewery_name')
                        
                        # Additional check: Does a brewery with this name already exist?
                        name_check = supabase.table('breweries').select('*').eq('name_en', brewery_name).execute()
                        
                        if name_check.data and len(name_check.data) > 0:
                            existing_brewery = name_check.data[0]
                            existing_url = existing_brewery.get('untappd_url')
                            
                            # Same brewery but different URL (e.g., vanity URL vs /w/ URL)
                            if existing_url != url:
                                logger.info(f"  ⏭️  Skipped: '{brewery_name}' already exists with different URL: {existing_url}")
                                continue
                        
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
                            # Check if record exists by untappd_url (primary unique key)
                            existing_res = supabase.table('breweries').select('id').eq('untappd_url', url).execute()
                            
                            if existing_res.data and len(existing_res.data) > 0:
                                # Update existing record
                                supabase.table('breweries').update(payload).eq('untappd_url', url).execute()
                                logger.info(f"  ✅ Updated: {brewery_name}")
                            else:
                                # Insert new record
                                supabase.table('breweries').insert(payload).execute()
                                logger.info(f"  ✅ Inserted: {brewery_name}")
                            
                            total_processed += 1
                        except Exception as e:
                            logger.error(f"  ❌ Error saving {url}: {e}")
                    else:
                        logger.warning(f"  ⚠️ Failed to scrape: {url}")

    logger.info(f"\n✨ Brewery enrichment completed. Processed {total_processed} breweries.")


"""
Gemini-only enrichment command.
Extracts brewery and beer names using Gemini API.
"""
import asyncio
import logging
from datetime import datetime, timezone
import os

from app.core.db import get_supabase_client
from app.core.config import settings
from app.services.gemini.extractor import GeminiExtractor
from app.services.store.brewery_manager import BreweryManager
from app.commands.enrich_untappd import process_beer_missing

logger = logging.getLogger(__name__)

async def enrich_gemini(limit: int = 50, shop_filter: str = None, keyword_filter: str = None, offline: bool = False, force_reprocess: bool = False):
    """
    Enrich beers with Gemini extraction only.
    Loops until all eligible beers are processed.
    """
    logger.info("=" * 70)
    logger.info("🤖 Gemini Enrichment (Supabase)")
    if offline:
        logger.info("📴 OFFLINE MODE: Skipping API calls. Only verifying/chaining existing data.")
    logger.info("=" * 70)
    
    target_msg = f"Target: All beers without Gemini data"
    if shop_filter:
        target_msg += f" (Shop: {shop_filter})"
    if keyword_filter:
        target_msg += f" (Keyword: {keyword_filter})"
        
    logger.info(f"{target_msg} (Batch size: {limit})")
    logger.info(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create Supabase client
    supabase = get_supabase_client()
    
    # Initialize extractor and brewery manager once
    extractor = GeminiExtractor()
    if not offline and not extractor.client:
        logger.error("\n❌ Error: Gemini API key not configured")
        return
    
    brewery_manager = BreweryManager()
    logger.info(f"📚 Loaded {len(brewery_manager.breweries)} known breweries as hints")
    
    # Initial count check
    logger.info(f"🔍 Checking for unprocessed items...")
    count_query = supabase.table('beer_info_view').select('count', count='exact', head=True)

    if offline:
        count_query = count_query.not_.is_('brewery_name_en', 'null').is_('untappd_url', 'null')
    else:
        # If force, we process everything matching filter, so count all
        if not force_reprocess:
             count_query = count_query.or_('brewery_name_en.is.null,untappd_url.is.null')

    if shop_filter:
        count_query = count_query.eq('shop', shop_filter)
        
    if keyword_filter:
        count_query = count_query.ilike('name', f'%{keyword_filter}%')
        
    count_res = count_query.execute()
    total_remaining = count_res.count
    
    logger.info(f"📊 Total items needing enrichment: {total_remaining}")
    
    if total_remaining == 0:
        logger.info("✨ No items need enrichment. Exiting.")
        return

    total_processed = 0
    total_enriched = 0
    total_errors = 0
    
    
    while True:
        if total_processed >= limit:
            logger.info(f"\n✋ Reached limit of {limit} items. Stopping.")
            break

        # Calculate remaining items to process
        remaining = limit - total_processed
        current_batch_size = min(100, remaining) # Cap batch size to Avoid massive fetches

        # Get beers that need Gemini enrichment OR Untappd enrichment
        logger.info(f"\n📂 Loading candidates from beer_info_view (Batch Target: {current_batch_size})...")
        
        query = supabase.table('beer_info_view').select('*')
        
        if offline:
            query = query.not_.is_('brewery_name_en', 'null').is_('untappd_url', 'null')
        else:
            if not force_reprocess:
                query = query.or_('brewery_name_en.is.null,untappd_url.is.null')
        
        if shop_filter:
            query = query.eq('shop', shop_filter)
            
        if keyword_filter:
            query = query.ilike('name', f'%{keyword_filter}%')
            
        response = query.order('first_seen', desc=True) \
            .limit(current_batch_size) \
            .execute()
            
        beers = response.data
        logger.info(f"  Found {len(beers)} beers in this batch")
        
        if not beers:
            logger.info("\n✨ No more beers found matching criteria!")
            break
            
        # Process batch
        for i, beer in enumerate(beers, 1):
            logger.info(f"\n{'='*70}")
            current_count = total_processed + i
            logger.info(f"[Batch Item {i}/{len(beers)} | Total {current_count}/{limit}] Processing: {beer.get('name', 'Unknown')[:60]}")
            logger.info(f"{'='*70}")
            
            updates = {}
            # Re-enrich if either English brewery or beer name is missing OR if forcing
            need_gemini = force_reprocess or (not beer.get('brewery_name_en') or not beer.get('beer_name_en'))
            
            try:
                if need_gemini:
                    if offline:
                         # Offline mode strictly chains, does not call Gemini
                         updates = False 
                    else:
                        # Check for known brewery hint in the beer name
                        known_brewery = None
                        brewery_match = brewery_manager.find_brewery_in_text(beer['name'])
                        if brewery_match:
                            known_brewery = brewery_match.get('name_en')
                            logger.info(f"  🏭 Found known brewery hint: {known_brewery}")
                        
                        logger.info("  🤖 Calling Gemini API...")
                        enriched_info = await extractor.extract_info(beer['name'], known_brewery=known_brewery)
                        
                        if enriched_info:
                            logger.info("  ✅ Gemini Extraction Success:")
                            logger.info(f"     Brewery (EN): {enriched_info.get('brewery_name_en')}")
                            logger.info(f"     Brewery (JP): {enriched_info.get('brewery_name_jp')}")
                            logger.info(f"     Beer (EN):    {enriched_info.get('beer_name_en')}")
                            if enriched_info.get('is_set'):
                                logger.info(f"     📦 Set Detected: YES (Skipping Untappd)")
                            
                            # Store enrichment data
                            gemini_payload = {
                                'url': beer['url'], # Key
                                'brewery_name_en': enriched_info.get('brewery_name_en'),
                                'brewery_name_jp': enriched_info.get('brewery_name_jp'),
                                'beer_name_en': enriched_info.get('beer_name_en'),
                                'beer_name_jp': enriched_info.get('beer_name_jp'),
                                'is_set': enriched_info.get('is_set', False),
                                'payload': enriched_info.get('raw_response'), # Save raw for debugging
                                'updated_at': datetime.now(timezone.utc).isoformat()
                            }

                            # Upsert to gemini_data table
                            try:
                                supabase.table('gemini_data').upsert(gemini_payload).execute()
                                logger.info(f"  💾 Saved to gemini_data table")
                            except Exception as e:
                                 logger.error(f"  ❌ Error saving to gemini_data: {e}")
                                 continue

                            # Merge for Untappd step (process_beer expects these in the beer dict or separate db fetch)
                            # We update the 'beer' object in memory so process_beer has the info
                            beer.update(gemini_payload)
                            updates = gemini_payload # Marker that we have updates
                            total_enriched += 1
                        else:
                            logger.warning("  ⚠️  Gemini returned no info")
                else:
                    logger.info("  ✅ Gemini data already exists. Skipping extraction.")
                    updates = True # Mark as "proceed to chain"
            
            except Exception as e:
                logger.error(f"  ❌ Error during Gemini processing: {e}")
                total_errors += 1
            
            # Chain Untappd processing if successful
            if updates:
                # If it's a set, we do NOT chain Untappd
                if isinstance(updates, dict) and updates.get('is_set'):
                     logger.info("  ⏭️  Skipping Untappd enrichment (Item is a Set/Merch)")
                else:
                    try:
                         logger.info("  🔗 Chaining Untappd enrichment...")
                         # Note: process_beer handles its own DB updates (to untappd_data/scraped_beers)
                         # Explicitly pass offline param
                         await process_beer_missing(beer, offline=offline)
                    except Exception as e:
                        logger.error(f"  ❌ Error chaining Untappd: {e}")
                        total_errors += 1
            else:
                 pass
                 
        total_processed += len(beers)
        
    # Final stats
    logger.info(f"\n{'='*70}")
    logger.info("📈 Final Statistics")
    logger.info(f"{'='*70}")
    logger.info(f"  Total processed: {total_processed}")
    logger.info(f"  Gemini enriched: {total_enriched}")
    logger.info(f"  Errors: {total_errors}")
    logger.info(f"\n  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    logger.info(f"\n{'='*70}")
    logger.info("✨ Gemini enrichment completed!")
    logger.info(f"{'='*70}")

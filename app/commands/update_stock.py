import asyncio
import logging
from typing import List, Optional
import httpx
from datetime import datetime
import os

from app.core.db import get_supabase_client
from app.services.stock_checker import check_stock_for_url

# Configure logging
logger = logging.getLogger(__name__)

BATCH_SIZE = 20
CONCURRENCY = 10

async def process_beer(client: httpx.AsyncClient, beer: dict, supabase) -> bool:
    """
    Checks stock for a single beer and updates DB if changed.
    Returns True if updated, False otherwise.
    """
    url = beer.get('url')
    shop = beer.get('shop')
    current_status = beer.get('stock_status')
    
    if not url: return False
    
    try:
        result = await check_stock_for_url(client, url, shop)
        new_status = result.get("stock_status", "Unknown")
        new_price = result.get("price")
        
        if new_status == "Error":
            logger.warning(f"Failed to check stock for {url}")
            return False
        
        # Prepare update data
        data = {
            "last_seen": datetime.now().isoformat()
        }
        
        # Add stock status if changed
        status_changed = new_status != current_status
        if status_changed:
            logger.info(f"[{shop}] Status Change: {beer['name']} | {current_status} -> {new_status}")
            data["stock_status"] = new_status
            
        # Add price if extracted
        if new_price:
            data["price"] = new_price
            
        # Update DB
        try:
            supabase.table('scraped_beers').update(data).eq('url', beer['url']).execute()
            return status_changed  # Return True only if status changed (for counting)
        except Exception as e:
            logger.error(f"DB Update failed for {beer['url']}: {e}")
            return False

    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        return False

async def update_stock_status(limit: int = None, shop_filter: str = None, sort_rating: bool = False):
    logger.info("Starting Stock Status Update...")
    supabase = get_supabase_client()
    
    # 1. Fetch beers
    if sort_rating:
        logger.info("Fetching beers sorted by Untappd Rating (DESC)...")
        # Query view for rating sort
        query = supabase.table('beer_info_view').select('name, url, shop, stock_status')\
            .order('untappd_rating', desc=True, nullsfirst=False)
    else:
        # Default fetch from scraped_beers
        query = supabase.table('scraped_beers').select('name, url, shop, stock_status')
    
    if shop_filter:
        query = query.eq('shop', shop_filter)
    
    # Add high limit to avoid Supabase's default 1000 row truncation
    res = query.limit(10000).execute()
    beers = res.data
    
    if limit:
        beers = beers[:limit]
        
    logger.info(f"Checking stock for {len(beers)} items...")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Semaphore for concurrency
        sem = asyncio.Semaphore(CONCURRENCY)
        
        async def bounded_process(beer):
            async with sem:
                return await process_beer(client, beer, supabase)
        
        # Batch processing to avoid massive queue
        updated_count = 0
        total_processed = 0
        
        # Split into chunks
        chunks = [beers[i:i + BATCH_SIZE] for i in range(0, len(beers), BATCH_SIZE)]
        
        for chunk in chunks:
            tasks = [bounded_process(beer) for beer in chunk]
            results = await asyncio.gather(*tasks)
            updated_count += sum(1 for r in results if r)
            total_processed += len(results)
            logger.info(f"Processed {total_processed}/{len(beers)}. Updated: {updated_count}")
            await asyncio.sleep(0.5) # Be nice to servers

    logger.info(f"Stock Update Complete. Total Checked: {len(beers)}, Updated: {updated_count}")

if __name__ == "__main__":
    # Test run
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(update_stock_status(limit=5))

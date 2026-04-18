import asyncio
import logging
from typing import List, Optional, Dict, Any, cast
import httpx
from datetime import datetime
import os

from ..core.db import get_supabase_client
from ..core.types import StockCheckResult
from ..services.stock_checker import check_stock_for_url

# Configure logging
logger: logging.Logger = logging.getLogger(__name__)

BATCH_SIZE: int = 20
CONCURRENCY: int = 10

async def process_beer(client: httpx.AsyncClient, beer: Dict[str, Any], supabase: Any) -> bool:
    """
    Checks stock for a single beer and updates DB if changed.
    Returns True if updated (meaning stock status changed), False otherwise.
    """
    url: Optional[str] = beer.get('url')
    shop: Optional[str] = beer.get('shop')
    current_status: Optional[str] = beer.get('stock_status')
    
    if not url or not shop: return False
    
    try:
        result: StockCheckResult = await check_stock_for_url(client, url, shop)
        new_status: str = result.get("stock_status", "Unknown")
        new_price: Optional[str] = result.get("price")
        
        if new_status == "Error":
            logger.warning(f"Failed to check stock for {url}")
            return False
        
        # Prepare update data
        data: Dict[str, Any] = {
            "last_seen": datetime.now().isoformat()
        }
        
        # Add stock status if changed
        status_changed: bool = new_status != current_status
        if status_changed:
            logger.info(f"[{shop}] Status Change: {beer.get('name', 'Unknown')} | {current_status} -> {new_status}")
            data["stock_status"] = new_status
            
        # Add price if extracted
        if new_price:
            data["price"] = new_price
            
        # Update DB
        try:
            supabase.table('scraped_beers').update(data).eq('url', url).execute()
            return status_changed
        except Exception as e:
            logger.error(f"DB Update failed for {url}: {e}")
            return False

    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        return False

async def update_stock_status(limit: Optional[int] = None, shop_filter: Optional[str] = None, sort_rating: bool = False) -> None:
    """
    Checks and updates stock status for existing items.
    """
    logger.info("Starting Stock Status Update...")
    supabase: Any = get_supabase_client()
    
    # 1. Fetch beers
    if sort_rating:
        logger.info("Fetching beers sorted by Untappd Rating (DESC)...")
        # Query view for rating sort
        query: Any = supabase.table('beer_info_view').select('name, url, shop, stock_status')\
            .order('untappd_rating', desc=True, nullsfirst=False)
    else:
        # Default fetch from scraped_beers
        query = supabase.table('scraped_beers').select('name, url, shop, stock_status')
    
    if shop_filter:
        query = query.eq('shop', shop_filter)
    
    # Add high limit to avoid Supabase's default 1000 row truncation
    res: Any = query.limit(10000).execute()
    beers: List[Dict[str, Any]] = res.data or []
    
    if limit:
        beers = beers[:limit]
        
    logger.info(f"Checking stock for {len(beers)} items...")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Semaphore for concurrency
        sem: asyncio.Semaphore = asyncio.Semaphore(CONCURRENCY)
        
        async def bounded_process(beer: Dict[str, Any]) -> bool:
            async with sem:
                return await process_beer(client, beer, supabase)
        
        # Batch processing to avoid massive queue
        updated_count: int = 0
        total_processed: int = 0
        
        # Split into chunks
        chunks: List[List[Dict[str, Any]]] = [beers[i:i + BATCH_SIZE] for i in range(0, len(beers), BATCH_SIZE)]
        
        for chunk in chunks:
            tasks: List[Any] = [bounded_process(beer) for beer in chunk]
            results: List[bool] = await asyncio.gather(*tasks)
            updated_count += sum(1 for r in results if r)
            total_processed += len(results)
            logger.info(f"Processed {total_processed}/{len(beers)}. Updated: {updated_count}")
            await asyncio.sleep(0.5)

    logger.info(f"Stock Update Complete. Total Checked: {len(beers)}, Updated: {updated_count}")

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    asyncio.run(update_stock_status(limit=5))

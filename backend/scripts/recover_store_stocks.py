"""
Comprehensive recovery script to restore accurate stock_status and prices
for stores affected by the stock checker bug:
- WITCH CRAFT MARKET
- ちょうせいや (Chouseiya)
- BEER VOLTA
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx
from bs4 import BeautifulSoup
from src.core.db import get_supabase_client, refresh_materialized_view
from src.scrapers import witch_craft_market
from src.services.stock_checker import (
    check_stock_for_url,
    check_stock_chouseiya,
    extract_price_chouseiya,
    check_stock_beervolta,
    extract_price_beervolta,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def get_store_stock_counts(supabase: Any, shop: str) -> Dict[str, int]:
    """Gets count of In Stock and Sold Out items for a shop."""
    res_in = supabase.table('scraped_beers').select('url', count='exact').eq('shop', shop).eq('stock_status', 'In Stock').execute()
    res_sold = supabase.table('scraped_beers').select('url', count='exact').eq('shop', shop).eq('stock_status', 'Sold Out').execute()
    return {
        "in_stock": res_in.count or 0,
        "sold_out": res_sold.count or 0,
    }

async def recover_witch_craft_market(supabase: Any):
    shop = "WITCH CRAFT MARKET"
    logger.info("=" * 60)
    logger.info(f"🔄 Restoring stock for {shop} via collection scrape...")
    counts_before = await get_store_stock_counts(supabase, shop)
    logger.info(f"[{shop}] Before: In Stock={counts_before['in_stock']}, Sold Out={counts_before['sold_out']}")

    products = await witch_craft_market.scrape_witch_craft_market(full_scrape=True)
    now_iso = datetime.now(timezone.utc).isoformat()
    
    in_stock_items = [p for p in products if p.get('stock_status') == 'In Stock']
    sold_out_items = [p for p in products if p.get('stock_status') == 'Sold Out']
    logger.info(f"[{shop}] Scraped {len(products)} products: {len(in_stock_items)} In Stock, {len(sold_out_items)} Sold Out")

    # Update in DB
    batch_size = 200
    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        for p in batch:
            data: Dict[str, Any] = {
                "stock_status": p.get("stock_status", "Sold Out"),
                "last_seen": now_iso
            }
            if p.get("price") and p["price"] != "Unknown":
                data["price"] = p["price"]
            try:
                supabase.table('scraped_beers').update(data).eq('url', p['url']).execute()
            except Exception as e:
                logger.error(f"[{shop}] Failed to update {p['url']}: {e}")

    counts_after = await get_store_stock_counts(supabase, shop)
    logger.info(f"[{shop}] After: In Stock={counts_after['in_stock']}, Sold Out={counts_after['sold_out']}")
    return counts_before, counts_after

async def recover_chouseiya_concurrent(supabase: Any):
    shop = "ちょうせいや"
    logger.info("=" * 60)
    logger.info(f"🔄 Restoring stock for {shop} via concurrent detail checks...")
    counts_before = await get_store_stock_counts(supabase, shop)
    logger.info(f"[{shop}] Before: In Stock={counts_before['in_stock']}, Sold Out={counts_before['sold_out']}")

    # Fetch all URLs for this shop
    res = supabase.table('scraped_beers').select('url, name').eq('shop', shop).execute()
    rows = res.data or []
    logger.info(f"[{shop}] Found {len(rows)} products to verify in DB.")

    now_iso = datetime.now(timezone.utc).isoformat()
    sem = asyncio.Semaphore(15)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    updated_count = 0
    in_stock_found = 0

    async def check_item(client: httpx.AsyncClient, item: Dict[str, Any]):
        nonlocal in_stock_found, updated_count
        url = item['url']
        async with sem:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    status = "Dead Link"
                    price = None
                elif resp.status_code == 200:
                    content = resp.content.decode('euc-jp', errors='replace')
                    soup = BeautifulSoup(content, 'lxml')
                    status = check_stock_chouseiya(soup)
                    price = extract_price_chouseiya(soup)
                else:
                    return

                if status == "In Stock":
                    in_stock_found += 1

                update_data: Dict[str, Any] = {
                    "stock_status": status,
                    "last_seen": now_iso
                }
                if price:
                    update_data["price"] = price

                supabase.table('scraped_beers').update(update_data).eq('url', url).execute()
                updated_count += 1
            except Exception as e:
                logger.warning(f"[{shop}] Error checking {url}: {e}")

    start_time = time.time()
    async with httpx.AsyncClient(timeout=15.0) as client:
        tasks = [check_item(client, r) for r in rows]
        await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    logger.info(f"[{shop}] Checked and updated {updated_count}/{len(rows)} items in {elapsed:.1f}s.")
    counts_after = await get_store_stock_counts(supabase, shop)
    logger.info(f"[{shop}] After: In Stock={counts_after['in_stock']}, Sold Out={counts_after['sold_out']}")
    return counts_before, counts_after

async def recover_beervolta_concurrent(supabase: Any):
    shop = "BEER VOLTA"
    logger.info("=" * 60)
    logger.info(f"🔄 Restoring stock for {shop} via concurrent detail checks...")
    counts_before = await get_store_stock_counts(supabase, shop)
    logger.info(f"[{shop}] Before: In Stock={counts_before['in_stock']}, Sold Out={counts_before['sold_out']}")

    # Fetch all URLs for this shop
    res = supabase.table('scraped_beers').select('url, name').eq('shop', shop).execute()
    rows = res.data or []
    logger.info(f"[{shop}] Found {len(rows)} products to verify in DB.")

    now_iso = datetime.now(timezone.utc).isoformat()
    sem = asyncio.Semaphore(15)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    updated_count = 0
    in_stock_found = 0

    async def check_item(client: httpx.AsyncClient, item: Dict[str, Any]):
        nonlocal in_stock_found, updated_count
        url = item['url']
        async with sem:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    status = "Dead Link"
                    price = None
                elif resp.status_code == 200:
                    content = resp.text
                    soup = BeautifulSoup(content, 'lxml')
                    status = check_stock_beervolta(soup)
                    price = extract_price_beervolta(soup)
                else:
                    return

                if status == "In Stock":
                    in_stock_found += 1

                update_data: Dict[str, Any] = {
                    "stock_status": status,
                    "last_seen": now_iso
                }
                if price:
                    update_data["price"] = price

                supabase.table('scraped_beers').update(update_data).eq('url', url).execute()
                updated_count += 1
            except Exception as e:
                logger.warning(f"[{shop}] Error checking {url}: {e}")

    start_time = time.time()
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        tasks = [check_item(client, r) for r in rows]
        await asyncio.gather(*tasks)

    elapsed = time.time() - start_time
    logger.info(f"[{shop}] Checked and updated {updated_count}/{len(rows)} items in {elapsed:.1f}s.")
    counts_after = await get_store_stock_counts(supabase, shop)
    logger.info(f"[{shop}] After: In Stock={counts_after['in_stock']}, Sold Out={counts_after['sold_out']}")
    return counts_before, counts_after

async def main():
    supabase = get_supabase_client()
    
    total_start = time.time()
    
    # 1. WITCH CRAFT MARKET
    wcm_before, wcm_after = await recover_witch_craft_market(supabase)
    
    # 2. ちょうせいや
    ch_before, ch_after = await recover_chouseiya_concurrent(supabase)
    
    # 3. BEER VOLTA
    bv_before, bv_after = await recover_beervolta_concurrent(supabase)
    
    # 4. Refresh materialized view
    logger.info("=" * 60)
    logger.info("⚡ Refreshing beer_info_view materialized view...")
    refresh_materialized_view(supabase, logger)
    
    total_elapsed = time.time() - total_start
    
    logger.info("=" * 60)
    logger.info(f"🎉 All stock recoveries completed in {total_elapsed:.1f}s!")
    logger.info(f"📊 Summary of In Stock counts:")
    logger.info(f"  - ちょうせいや:         {ch_before['in_stock']} -> {ch_after['in_stock']}")
    logger.info(f"  - WITCH CRAFT MARKET: {wcm_before['in_stock']} -> {wcm_after['in_stock']}")
    logger.info(f"  - BEER VOLTA:         {bv_before['in_stock']} -> {bv_after['in_stock']}")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

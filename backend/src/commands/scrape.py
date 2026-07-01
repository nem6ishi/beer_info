"""
Cloud scraper that writes directly to Supabase.
Orchestrates the scraping process for multiple beer sites.
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set, Any, Union

from ..core.db import get_supabase_client, async_execute
from ..core.types import ScrapedProduct
from ..scrapers import beervolta, chouseiya, ichigo_ichie, arome, maruho, antenna_america

logger = logging.getLogger(__name__)

def parse_price(price_str: Optional[str]) -> Optional[int]:
    """
    Extract numeric value from price string.
    """
    if not price_str:
        return None
    try:
        # Remove non-digits
        clean: str = re.sub(r'[^0-9]', '', str(price_str))
        if clean:
            return int(clean)
        return None
    except Exception:
        return None

async def run_and_save_store(
    scraper_coro: Any,
    display_name: str,
    supabase: Any,
    existing_data: Dict[str, Dict[str, Any]],
    new_only: bool,
    reset_first_seen: bool,
    base_time: datetime,
    store_index: int,
    timeout: int = 420,
) -> tuple[int, int, int]:
    """
    Run a single scraper with a timeout, process items, and upsert directly to Supabase.
    Returns (new_count, updated_count, upserted_count).
    """
    logger.info(f"🚀 Starting scraper for {display_name} (timeout: {timeout}s)...")
    try:
        items: List[ScrapedProduct] = await asyncio.wait_for(scraper_coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"  ❌ {display_name}: Scraper timed out after {timeout}s")
        return 0, 0, 0
    except Exception as e:
        logger.error(f"  ❌ {display_name}: Scraper error - {e}")
        return 0, 0, 0

    if not items:
        logger.info(f"  ✅ {display_name}: 0 items fetched.")
        return 0, 0, 0

    logger.info(f"  ✅ {display_name}: {len(items)} items fetched. Preparing upsert...")

    current_time_iso: str = datetime.now(timezone.utc).isoformat()
    new_count: int = 0
    updated_count: int = 0
    beers_to_upsert: List[Dict[str, Any]] = []

    # Items are likely Newest -> Oldest (Page 1 top -> Page N bottom)
    items_to_process: List[ScrapedProduct] = list(reversed(items))

    for idx, new_item in enumerate(items_to_process):
        url: str = new_item.get('url', '')
        if not url:
            continue

        existing: Optional[Dict[str, Any]] = existing_data.get(url)
        is_restock: bool = False

        if existing:
            prev_stock: str = (existing.get('stock_status') or '').lower()
            new_stock: str = (new_item.get('stock_status') or '').lower()

            was_sold_out: bool = 'sold' in prev_stock or 'out' in prev_stock
            is_now_available: bool = not ('sold' in new_stock or 'out' in new_stock)

            if was_sold_out and is_now_available:
                is_restock = True
                logger.info(f"  🔄 {display_name} Restock: {new_item.get('name', 'Unknown')[:50]}")

        # Assign increasing timestamp separated by store index and item index
        item_time: datetime = base_time + timedelta(seconds=store_index, microseconds=idx)
        item_time_iso: str = new_item.get('first_seen') or item_time.isoformat()

        beer_data: Dict[str, Any] = {
            'url': url,
            'name': new_item.get('name'),
            'price': new_item.get('price'),
            'price_num': parse_price(new_item.get('price')),
            'image': new_item.get('image'),
            'stock_status': new_item.get('stock_status'),
            'shop': new_item.get('shop'),
            'last_seen': current_time_iso,
        }

        if existing and not reset_first_seen:
            if new_only and not is_restock:
                continue

            if is_restock:
                beer_data['first_seen'] = item_time_iso
            else:
                beer_data['first_seen'] = existing.get('first_seen')

            if existing.get('untappd_url'):
                beer_data['untappd_url'] = existing.get('untappd_url')

            updated_count += 1
        else:
            beer_data['first_seen'] = item_time_iso
            new_count += 1

        beers_to_upsert.append(beer_data)

    if beers_to_upsert:
        batch_size: int = 1000
        for i in range(0, len(beers_to_upsert), batch_size):
            batch: List[Dict[str, Any]] = beers_to_upsert[i:i + batch_size]
            try:
                await async_execute(supabase.table('scraped_beers').upsert(batch, on_conflict='url'))
                logger.info(f"  💾 {display_name}: Upserted batch {i // batch_size + 1} ({len(batch)} items)")
            except Exception as e:
                logger.error(f"  ❌ {display_name}: Error upserting batch: {e}")

    return new_count, updated_count, len(beers_to_upsert)


async def scrape_to_supabase(
    limit: Optional[int] = None, 
    new_only: bool = False, 
    full_scrape: bool = False, 
    reset_first_seen: bool = False
) -> None:
    """
    Scrape and write directly to Supabase (scraped_beers table).
    """
    logger.info("=" * 60)
    logger.info("🍺 Cloud Scraper (writing to Supabase: scraped_beers)")
    if new_only:
        logger.info("🍺 新商品スクレイプ (New Product Scrape) ENABLED: 既存商品が30件続いたら停止")
    if full_scrape:
        logger.info("🔥 全件スクレイプ (Full Scrape) ENABLED: 停止リミットを無視して全件取得")
    logger.info("=" * 60)
    
    supabase: Any = get_supabase_client()
    
    # Get existing beers from Supabase to check for updates vs new items
    logger.info("\n📂 Loading existing beers from scraped_beers...")
    
    all_existing_beers: List[Dict[str, Any]] = []
    chunk_size: int = 1000
    start: int = 0
    
    while True:
        # Fetch in chunks
        response: Any = await async_execute(supabase.table('scraped_beers').select('url, first_seen, stock_status, untappd_url').range(start, start + chunk_size - 1))
        
        if not response.data:
            break
            
        all_existing_beers.extend(response.data)
        
        if len(response.data) < chunk_size:
            break
            
        start += chunk_size

    existing_data: Dict[str, Dict[str, Any]] = {beer['url']: beer for beer in all_existing_beers}
    existing_urls: Set[str] = set(existing_data.keys())
    logger.info(f"  Loaded {len(existing_data)} existing beers (Complete)")
    
    timeout_sec: int = int(os.getenv("SCRAPER_TIMEOUT", "420"))
    base_time: datetime = datetime.now(timezone.utc)

    # Run scrapers and save independently per store
    logger.info(f"\n🔍 Running scrapers and saving directly per store (timeout: {timeout_sec}s)...")
    tasks = [
        run_and_save_store(
            beervolta.scrape_beervolta(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
            'BeerVolta', supabase, existing_data, new_only, reset_first_seen, base_time, 0, timeout_sec
        ),
        run_and_save_store(
            chouseiya.scrape_chouseiya(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
            'Chouseiya', supabase, existing_data, new_only, reset_first_seen, base_time, 1, timeout_sec
        ),
        run_and_save_store(
            ichigo_ichie.scrape_ichigo_ichie(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
            'Ichigo Ichie', supabase, existing_data, new_only, reset_first_seen, base_time, 2, timeout_sec
        ),
        run_and_save_store(
            arome.scrape_arome(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
            'Arôme', supabase, existing_data, new_only, reset_first_seen, base_time, 3, timeout_sec
        ),
        run_and_save_store(
            maruho.scrape_maruho(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
            'Maruho', supabase, existing_data, new_only, reset_first_seen, base_time, 4, timeout_sec
        ),
        run_and_save_store(
            antenna_america.scrape_antenna_america(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
            'Antenna America', supabase, existing_data, new_only, reset_first_seen, base_time, 5, timeout_sec
        ),
    ]

    store_results = await asyncio.gather(*tasks)

    total_new = sum(r[0] for r in store_results)
    total_updated = sum(r[1] for r in store_results)
    total_upserted = sum(r[2] for r in store_results)

    logger.info(f"\n{'='*60}")
    logger.info("📈 Statistics:")
    logger.info(f"  🆕 New beers: {total_new}")
    logger.info(f"  🔄 Updated beers: {total_updated}")
    logger.info(f"  📦 Total upserted: {total_upserted}")
    logger.info("=" * 60)
    logger.info("✨ Scraping completed!")
    logger.info("=" * 60)

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

from ..core.db import get_supabase_client, async_execute, refresh_materialized_view
from ..core.types import ScrapedProduct
from ..scrapers import beervolta, chouseiya, ichigo_ichie, arome, maruho, antenna_america, witch_craft_market

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
) -> tuple[int, int, int, str]:
    """
    Run a single scraper with a timeout, process items, and upsert directly to Supabase.
    Returns (new_count, updated_count, upserted_count, status).
    status: 'ok' | 'empty' | 'error' | 'timeout'
    """
    logger.info(f"🚀 Starting scraper for {display_name} (timeout: {timeout}s)...")
    try:
        items: List[ScrapedProduct] = await asyncio.wait_for(scraper_coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"  ❌ {display_name}: Scraper timed out after {timeout}s")
        print(f"::error title=Scraper timeout::{display_name} timed out after {timeout}s", flush=True)
        return 0, 0, 0, "timeout"
    except Exception as e:
        logger.error(f"  ❌ {display_name}: Scraper error - {e}")
        print(f"::error title=Scraper error::{display_name} error: {e}", flush=True)
        return 0, 0, 0, "error"

    if not items:
        logger.warning(f"  ⚠️ {display_name}: 0 items fetched.")
        print(f"::warning title=Scraper empty::{display_name} returned 0 items", flush=True)
        return 0, 0, 0, "empty"

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
        scraped_first_seen: Optional[str] = new_item.get('first_seen')
        item_time_iso: str = scraped_first_seen or item_time.isoformat()

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

            # If shop provides an explicit item creation/published date (first_seen), always prioritize it
            if scraped_first_seen:
                beer_data['first_seen'] = scraped_first_seen
            elif is_restock:
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
        try:
            refresh_materialized_view(supabase, logger)
        except Exception as e:
            logger.warning(f"  ⚠️ {display_name}: Error refreshing view: {e}")

    return new_count, updated_count, len(beers_to_upsert), "ok"


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
    
    timeout_sec: int = int(os.getenv("SCRAPER_TIMEOUT", "1800"))
    base_time: datetime = datetime.now(timezone.utc)

    # Store configurations: (name, coroutine)
    store_configs = [
        ('BeerVolta', beervolta.scrape_beervolta(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 0),
        ('Chouseiya', chouseiya.scrape_chouseiya(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 1),
        ('Ichigo Ichie', ichigo_ichie.scrape_ichigo_ichie(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 2),
        ('Arôme', arome.scrape_arome(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 3),
        ('Maruho', maruho.scrape_maruho(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 4),
        ('Antenna America', antenna_america.scrape_antenna_america(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 5),
        ('WITCH CRAFT MARKET', witch_craft_market.scrape_witch_craft_market(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape), 6),
    ]

    # Run scrapers and save independently per store
    logger.info(f"\n🔍 Running scrapers and saving directly per store (timeout: {timeout_sec}s)...")
    tasks = [
        run_and_save_store(coro, name, supabase, existing_data, new_only, reset_first_seen, base_time, idx, timeout_sec)
        for (name, coro, idx) in store_configs
    ]

    store_results = await asyncio.gather(*tasks)

    total_new = sum(r[0] for r in store_results)
    total_updated = sum(r[1] for r in store_results)
    total_upserted = sum(r[2] for r in store_results)

    logger.info(f"\n{'='*60}")
    logger.info("📈 Statistics:")
    for (name, _, _), r in zip(store_configs, store_results):
        status_icon = "✅" if r[3] == "ok" else ("⚠️" if r[3] == "empty" else "❌")
        logger.info(f"  {status_icon} {name:20}: new={r[0]}, updated={r[1]}, upserted={r[2]}, status={r[3]}")
    logger.info(f"  🆕 New beers: {total_new}")
    logger.info(f"  🔄 Updated beers: {total_updated}")
    logger.info(f"  📦 Total upserted: {total_upserted}")
    logger.info("=" * 60)
    logger.info("✨ Scraping completed!")
    logger.info("=" * 60)

    # Write GitHub Step Summary if running in GitHub Actions
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write("### 🍺 Scrape Results Summary\n\n")
                f.write("| Shop | Status | New | Updated | Upserted |\n")
                f.write("| --- | :---: | :---: | :---: | :---: |\n")
                for (name, _, _), r in zip(store_configs, store_results):
                    badge = "✅ OK" if r[3] == "ok" else ("⚠️ 0 Items" if r[3] == "empty" else f"❌ {r[3].upper()}")
                    f.write(f"| {name} | {badge} | {r[0]} | {r[1]} | {r[2]} |\n")
                f.write(f"\n**Total New**: {total_new} | **Total Updated**: {total_updated} | **Total Upserted**: {total_upserted}\n")
        except Exception as e:
            logger.warning(f"Failed to write GITHUB_STEP_SUMMARY: {e}")

    # Check for failure conditions to alert CI
    error_stores = [name for (name, _, _), r in zip(store_configs, store_results) if r[3] in ("error", "timeout")]
    empty_stores = [name for (name, _, _), r in zip(store_configs, store_results) if r[3] == "empty"]

    if error_stores:
        raise RuntimeError(f"Scraper failed for stores: {', '.join(error_stores)}")
    if len(empty_stores) >= 4:
        raise RuntimeError(f"Majority of scrapers returned 0 items ({len(empty_stores)}/7): {', '.join(empty_stores)}")

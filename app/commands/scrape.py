"""
Cloud scraper that writes directly to Supabase.
Orchestrates the scraping process for multiple beer sites.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from app.core.db import get_supabase_client
from app.scrapers import beervolta, chouseiya, ichigo_ichie, arome

logger = logging.getLogger(__name__)

def parse_price(price_str):
    """
    Extract numeric value from price string.
    """
    if not price_str:
        return None
    try:
        # Remove non-digits
        clean = re.sub(r'[^0-9]', '', str(price_str))
        if clean:
            return int(clean)
        return None
    except:
        return None

async def scrape_to_supabase(limit: int = None, new_only: bool = False, full_scrape: bool = False, reset_first_seen: bool = False):
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
    
    supabase = get_supabase_client()
    
    # Get existing beers from Supabase to check for updates vs new items
    logger.info("\n📂 Loading existing beers from scraped_beers...")
    
    all_existing_beers = []
    chunk_size = 1000
    start = 0
    
    while True:
        # Fetch in chunks
        response = supabase.table('scraped_beers').select('url, first_seen, stock_status, untappd_url').range(start, start + chunk_size - 1).execute()
        
        if not response.data:
            break
            
        all_existing_beers.extend(response.data)
        
        if len(response.data) < chunk_size:
            break
            
        start += chunk_size
        # logger.info(f"  Loaded {len(all_existing_beers)} items...", end='\r') # Logging doesn't support 'end'

    existing_data = {beer['url']: beer for beer in all_existing_beers}
    existing_urls = set(existing_data.keys())
    logger.info(f"  Loaded {len(existing_data)} existing beers (Complete)")
    
    # Define scrapers
    # Note: Ensure these modules have the expected interface: scrape_*(limit, existing_urls, full_scrape)
    scraper_names = ['beervolta', 'chouseiya', 'ichigo_ichie', 'arome']
    display_names = ['BeerVolta', 'Chouseiya', 'Ichigo Ichie', 'Arôme']

    # Run scrapers in parallel
    logger.info("\n🔍 Running scrapers in parallel...")
    results = await asyncio.gather(
        beervolta.scrape_beervolta(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
        chouseiya.scrape_chouseiya(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
        ichigo_ichie.scrape_ichigo_ichie(limit=limit, existing_urls=existing_urls if new_only else None, full_scrape=full_scrape),
        arome.scrape_arome(limit=limit, existing_urls=existing_urls, full_scrape=full_scrape), # Arome matches signature
        return_exceptions=True
    )
    
    # Process each scraper result separately to maintain per-store order
    scraper_results = []
    
    for i, res in enumerate(results):
        if i >= len(display_names):
             display_name = f"Scraper {i}"
        else:
             display_name = display_names[i]
        
        items = []
        
        if isinstance(res, list):
            items = res
        elif isinstance(res, Exception):
            logger.error(f"  ❌ {display_name}: Error - {res}")
            scraper_results.append([])
            continue
            
        logger.info(f"  ✅ {display_name}: {len(items)} items")
        scraper_results.append(items)

    # Flatten for count
    new_scraped_items = [item for sublist in scraper_results for item in sublist]
    logger.info(f"\n📊 Total scraped: {len(new_scraped_items)} items")
    
    # Process and upsert
    current_time = datetime.now(timezone.utc)
    current_time_iso = current_time.isoformat()
    
    new_count = 0
    updated_count = 0
    
    beers_to_upsert = []
    
    global_index = 0
    base_time = datetime.now(timezone.utc)
    
    for store_items in scraper_results:
        if not store_items:
            continue
            
        # Items are likely Newest -> Oldest (Page 1 top -> Page N bottom)
        # We want to process Oldest -> Newest to assign timestamps correctly for "First Seen" if strictly sequential
        # But actually, 'first_seen' is set to NOW for new items.
        # The 'global_index' logic in original script was to prevent collision or maintain sort stability?
        # Original: assigned increasing timestamp with microseconds.
        # So we keep the reverse logic.
        items_to_process = list(reversed(store_items))

        for new_item in items_to_process:
            url = new_item.get('url')
            if not url:
                continue
            
            existing = existing_data.get(url)
            is_restock = False
            
            if existing:
                prev_stock = (existing.get('stock_status') or '').lower()
                new_stock = (new_item.get('stock_status') or '').lower()
                
                was_sold_out = 'sold' in prev_stock or 'out' in prev_stock
                is_now_available = not ('sold' in new_stock or 'out' in new_stock)
                
                if was_sold_out and is_now_available:
                    is_restock = True
                    logger.info(f"  🔄 Restock: {new_item.get('name', 'Unknown')[:50]}")

            # Assign increasing timestamp with minimal difference
            item_time = base_time + timedelta(microseconds=global_index)
            item_time_iso = item_time.isoformat()
            global_index += 1

            beer_data = {
                'url': url,
                'name': new_item.get('name'),
                'price': new_item.get('price'),
                'price_value': parse_price(new_item.get('price')),
                'image': new_item.get('image'),
                'stock_status': new_item.get('stock_status'),
                'shop': new_item.get('shop'),
                'last_seen': current_time_iso,
            }
            
            if existing and not reset_first_seen:
                # In New Product Scrape mode, skip updating existing items unless it's a restock
                if new_only and not is_restock:
                    continue

                # Update existing beer
                if is_restock:
                    beer_data['first_seen'] = item_time_iso
                else:
                    beer_data['first_seen'] = existing.get('first_seen')
                
                # Preserve link to Untappd Data
                if existing.get('untappd_url'):
                    beer_data['untappd_url'] = existing.get('untappd_url')
                
                updated_count += 1
            else:
                # New beer
                beer_data['first_seen'] = item_time_iso
                new_count += 1
            
            beers_to_upsert.append(beer_data)
    
    # Batch upsert to Supabase
    if beers_to_upsert:
        batch_size = 1000
        for i in range(0, len(beers_to_upsert), batch_size):
            batch = beers_to_upsert[i:i + batch_size]
            logger.info(f"\n💾 Upserting batch {i // batch_size + 1} ({len(batch)} beers)...")
            try:
                # Upsert to scraped_beers
                supabase.table('scraped_beers').upsert(batch, on_conflict='url').execute()
                logger.info(f"  ✅ Upserted {len(batch)} beers")
            except Exception as e:
                logger.error(f"  ❌ Error upserting batch: {e}")
    
    logger.info(f"\n{'='*60}")
    logger.info("📈 Statistics:")
    logger.info(f"  🆕 New beers: {new_count}")
    logger.info(f"  🔄 Updated beers: {updated_count}")
    logger.info(f"  📦 Total upserted: {len(beers_to_upsert)}")
    logger.info("=" * 60)
    logger.info("✨ Scraping completed!")
    logger.info("=" * 60)

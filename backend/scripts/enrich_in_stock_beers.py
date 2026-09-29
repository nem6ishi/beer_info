import asyncio
import logging
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.llm.gemini_extractor import GeminiExtractor
from backend.src.services.store.brewery_manager import BreweryManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def enrich_in_stock(shop_filter: Optional[str] = None, limit: Optional[int] = None):
    sb = get_supabase_client()
    extractor = GeminiExtractor()
    bm = BreweryManager()
    
    logger.info("=" * 70)
    logger.info("📦 Fetching in-stock items missing from gemini_data...")
    if shop_filter:
        logger.info(f"🏪 Shop Filter: {shop_filter}")
    logger.info("=" * 70)

    # 1. Fetch in-stock beers from scraped_beers
    all_in_stock = []
    offset = 0
    while True:
        query = sb.table('scraped_beers').select('url, name, shop, first_seen').eq('stock_status', 'In Stock')
        if shop_filter:
            query = query.eq('shop', shop_filter)
        res = query.order('first_seen', desc=True).range(offset, offset + 999).execute()
        rows = res.data or []
        if not rows:
            break
        all_in_stock.extend(rows)
        offset += 1000
        if len(rows) < 1000:
            break

    logger.info(f"Total in-stock items found: {len(all_in_stock)}")

    # 2. Fetch existing urls in gemini_data
    gemini_urls = set()
    offset = 0
    while True:
        res = sb.table('gemini_data').select('url').range(offset, offset + 999).execute()
        rows = res.data or []
        if not rows:
            break
        for r in rows:
            gemini_urls.add(r['url'])
        offset += 1000
        if len(rows) < 1000:
            break

    # 3. Filter for items needing extraction
    targets = [b for b in all_in_stock if b['url'] not in gemini_urls]
    logger.info(f"🎯 Target items needing gemini extraction: {len(targets)}")

    if limit and limit > 0:
        targets = targets[:limit]
        logger.info(f"Applied limit: processing first {len(targets)} items")

    if not targets:
        logger.info("✨ No items need extraction!")
        return

    # 4. Extract and batch save
    batch_payloads = []
    success_count = 0
    error_count = 0

    for idx, item in enumerate(targets, 1):
        url = item['url']
        name = item['name']
        shop = item['shop']
        
        logger.info(f"\n[{idx}/{len(targets)}] ({shop}) {name}")
        
        # Look for known brewery hints
        known_breweries = bm.find_breweries_in_text(name)
        known_hint = known_breweries[0]['name_en'] if known_breweries else None
        
        try:
            extracted = await extractor.extract_info(
                product_name=name,
                known_brewery=known_hint,
                shop=shop
            )
            
            if extracted:
                now_iso = datetime.now(timezone.utc).isoformat()
                payload = {
                    'url': url,
                    'brewery_name_en': extracted.get('brewery_name_en'),
                    'brewery_name_jp': extracted.get('brewery_name_jp'),
                    'beer_name_en': extracted.get('beer_name_en'),
                    'beer_name_jp': extracted.get('beer_name_jp'),
                    'beer_name_core': extracted.get('beer_name_core'),
                    'search_hint': extracted.get('search_hint'),
                    'product_type': extracted.get('product_type') or 'beer',
                    'is_set': extracted.get('is_set', False),
                    'payload': extracted,
                    'updated_at': now_iso,
                }
                batch_payloads.append(payload)
                success_count += 1
                logger.info(f"  ✅ Extracted: Brewery='{extracted.get('brewery_name_en')}', Beer='{extracted.get('beer_name_en')}', Type='{extracted.get('product_type')}'")
            else:
                logger.warning(f"  ❌ Failed to extract info for: {name}")
                error_count += 1
        except Exception as e:
            logger.error(f"  ❌ Error extracting {name}: {e}")
            error_count += 1

        # Save batch every 10 items
        if len(batch_payloads) >= 10:
            sb.table('gemini_data').upsert(batch_payloads, on_conflict='url').execute()
            logger.info(f"  💾 Saved batch of {len(batch_payloads)} items to gemini_data")
            batch_payloads.clear()

    # Save any remaining
    if batch_payloads:
        sb.table('gemini_data').upsert(batch_payloads, on_conflict='url').execute()
        logger.info(f"  💾 Saved final batch of {len(batch_payloads)} items to gemini_data")
        batch_payloads.clear()

    logger.info("\n" + "=" * 70)
    logger.info(f"🏁 Extraction Finished! Success: {success_count}, Errors: {error_count}")
    logger.info("🔄 Refreshing beer_info_view...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ View refreshed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich in-stock beers with Gemini extraction")
    parser.add_argument("--shop", type=str, default=None, help="Filter by shop name")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of items to process")
    args = parser.parse_args()

    asyncio.run(enrich_in_stock(shop_filter=args.shop, limit=args.limit))

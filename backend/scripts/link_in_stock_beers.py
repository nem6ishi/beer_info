import asyncio
import logging
import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.searcher import get_untappd_url
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def link_in_stock(shop_filter: Optional[str] = None, limit: Optional[int] = 50, force: bool = False):
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🍺 Linking In-Stock Extracted Beers to Untappd")
    if shop_filter:
        logger.info(f"🏪 Shop Filter: {shop_filter}")
    logger.info("=" * 70)

    # 1. Fetch in-stock unlinked beers
    all_in_stock = []
    offset = 0
    while True:
        query = sb.table('scraped_beers').select('url, name, shop, first_seen').eq('stock_status', 'In Stock').is_('untappd_url', 'null')
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

    logger.info(f"Total in-stock unlinked items: {len(all_in_stock)}")
    if not all_in_stock:
        logger.info("✨ No in-stock unlinked items found!")
        return

    # 2. Get gemini_data for these URLs
    urls = [b['url'] for b in all_in_stock]
    gemini_map = {}
    
    # Chunk by 200 for PostgREST
    for i in range(0, len(urls), 200):
        chunk = urls[i:i+200]
        res = sb.table('gemini_data').select(
            'url, brewery_name_en, brewery_name_jp, beer_name_en, beer_name_jp, beer_name_core, search_hint, product_type, is_set'
        ).in_('url', chunk).execute()
        for r in (res.data or []):
            gemini_map[r['url']] = r

    # 3. Filter for valid single beers
    candidates = []
    for b in all_in_stock:
        g = gemini_map.get(b['url'])
        if not g:
            continue
        # Skip sets, glasses, other non-beer items
        if g.get('is_set') or g.get('product_type') in ['set', 'glass', 'other']:
            continue
        # Must have at least beer name or brewery name
        if not (g.get('beer_name_en') or g.get('beer_name_jp') or g.get('brewery_name_en')):
            continue
        candidates.append((b, g))

    logger.info(f"🎯 Target valid beers with gemini_data ready to search: {len(candidates)}")

    if limit and limit > 0:
        candidates = candidates[:limit]
        logger.info(f"Processing first {len(candidates)} items (limit={limit})")

    success_count = 0
    failure_count = 0

    for idx, (beer, gem) in enumerate(candidates, 1):
        url = beer['url']
        name = beer['name']
        shop = beer['shop']
        
        brewery_en = gem.get('brewery_name_en')
        beer_en = gem.get('beer_name_en')
        beer_jp = gem.get('beer_name_jp')
        beer_core = gem.get('beer_name_core')
        search_hint = gem.get('search_hint')

        logger.info(f"\n[{idx}/{len(candidates)}] ({shop}) {name}")
        logger.info(f"  Gemini: Brewery='{brewery_en}', Beer='{beer_en}', Core='{beer_core}'")

        try:
            search_res = await get_untappd_url(
                brewery_name=brewery_en or "",
                beer_name=beer_en or "",
                beer_name_jp=beer_jp,
                beer_name_core=beer_core,
                search_hint=search_hint,
                original_title=name,
            )

            found_url = search_res.get('url')
            if found_url and search_res.get('success'):
                logger.info(f"  🎉 Found Match: {found_url}")
                
                # 1. Scrape details
                details = await scrape_beer_details(found_url)
                if details:
                    payload = map_details_to_payload(details)
                    payload["untappd_url"] = found_url
                    payload["fetched_at"] = now_iso
                    sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                    logger.info(f"  💾 Saved to untappd_data: {details.get('untappd_beer_name')} ({details.get('style')})")

                # 2. Update scraped_beers and gemini_data
                sb.table("scraped_beers").update({"untappd_url": found_url}).eq("url", url).execute()
                sb.table("gemini_data").update({"untappd_url": found_url}).eq("url", url).execute()
                
                # 3. Mark failure resolved if any
                sb.table("untappd_search_failures").update({
                    "resolved": True,
                    "resolved_at": now_iso,
                    "notes": "Resolved in link_in_stock batch"
                }).eq("product_url", url).execute()

                success_count += 1
            else:
                reason = search_res.get('failure_reason', 'unknown')
                logger.warning(f"  ❌ No Untappd match found ({reason})")
                failure_count += 1

            # Be gentle with Untappd rate limits
            await asyncio.sleep(2.0)

        except Exception as e:
            logger.error(f"  ❌ Error searching Untappd for {name}: {e}")
            failure_count += 1

    logger.info("\n" + "=" * 70)
    logger.info(f"🏁 Finished! Matches linked: {success_count}, Unmatched: {failure_count}")
    logger.info("🔄 Refreshing beer_info_view...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ View refreshed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link in-stock beers with gemini_data to Untappd")
    parser.add_argument("--shop", type=str, default=None, help="Filter by shop name")
    parser.add_argument("--limit", type=int, default=50, help="Limit number of items to process")
    args = parser.parse_args()

    asyncio.run(link_in_stock(shop_filter=args.shop, limit=args.limit))

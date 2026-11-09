import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TARGET_ITEMS = [
    # 1. Y.Market - Lupulin Nectar ∀ (ちょうせいや)
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001789",
        "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケットブルーイング",
            "beer_name_en": "Lupulin Nectar ∀",
            "beer_name_jp": "ルプリンネクター ターンエー",
            "beer_name_core": "Lupulin Nectar ∀",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871"
        }
    },
    # 2. Y.Market - Lupulin Nectar ∀ (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8293",
        "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケットブルーイング",
            "beer_name_en": "Lupulin Nectar ∀",
            "beer_name_jp": "ルプリンネクター ターンエー",
            "beer_name_core": "Lupulin Nectar ∀",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-lupulin-nectar/7663871"
        }
    },
    # 3. Stem Ciders - Hibiscus Session (Antenna America)
    {
        "url": "https://www.antenna-america.com/products/c004-c12002",
        "untappd_url": "https://untappd.com/b/stem-ciders-hibiscus-session-apple-cider/6606036",
        "gemini_update": {
            "brewery_name_en": "Stem Ciders",
            "brewery_name_jp": "ステムサイダーズ",
            "beer_name_en": "Hibiscus Session Apple Cider",
            "beer_name_jp": "ハイビスカス セッション",
            "beer_name_core": "Hibiscus Session",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/stem-ciders-hibiscus-session-apple-cider/6606036"
        }
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info(f"Starting correction for {len(TARGET_ITEMS)} items...")

    # Unique untappd URLs to scrape
    untappd_urls = set(item["untappd_url"] for item in TARGET_ITEMS)
    for u_url in untappd_urls:
        logger.info(f"Scraping Untappd details for {u_url}...")
        details = await scrape_beer_details(u_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = u_url
            payload["fetched_at"] = now_iso
            sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url"))
            logger.info(f"  ✅ Saved to untappd_data: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {u_url}")
        await asyncio.sleep(0.5)

    for item in TARGET_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"Updating DB for {url} -> {untappd_url}")

        # Update gemini_data
        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url"))

        # Update scraped_beers
        sync_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url))

        # Mark failure as resolved in untappd_search_failures
        sync_execute(sb.table("untappd_search_failures").update({
            "resolved": True
        }).eq("product_url", url))
        logger.info(f"  ✅ Resolved & linked: {url}")

    # Refresh materialized view
    logger.info("Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("🎉 Done! Materialized view refreshed successfully.")

if __name__ == "__main__":
    asyncio.run(main())

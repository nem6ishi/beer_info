import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 誤紐付けの是正対象
CORRECTION_TARGETS = [
    {
        "product_url": "https://beer-chouseiya.shop/shopdetail/000000000464",
        "name": "【Schlenkerla  Märzen/Heller】",
        "old_untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-helles-marzen-special-edition-unfiltriert-pale-edition/6205353",
        "new_untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-marzen/471",
        "notes": "定番のメルツェン(5.1%)。限定無濾過版(6205353)から定番(471)へ是正"
    },
    {
        "product_url": "https://beer-chouseiya.shop/shopdetail/000000002272",
        "name": "【Schlenkerla Urbock/Heller】",
        "old_untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-schlenkerla-urbock-eisbock/5737345",
        "new_untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-urbock/10052",
        "notes": "冬季限定ウアボック(6.5%)。アイスボック(5737345)から定番ウアボック(10052)へ是正"
    }
]

# 2. ローリング再取得・最新化対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/ace-cider-mango-cider/3865969",
    "https://untappd.com/b/fruktstereo-chateau-nubbgatan-red/6502173",
    "https://untappd.com/b/evil-twin-brewing-nyc-isn-t-brooklyn-a-little-sketchy-why-would-you-live-there/3430672",
    "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-original-tap07/11982",
    "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-marzen/471",
    "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-urbock/10052"
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Audit & Enrichment Pipeline (v3)")
    logger.info("=" * 70)

    # 1. 誤紐付けの是正
    logger.info("\n[1] Correcting mismatched Untappd URLs...")
    for item in CORRECTION_TARGETS:
        p_url = item["product_url"]
        new_u_url = item["new_untappd_url"]

        sb_res = sb.table("scraped_beers").update({
            "untappd_url": new_u_url,
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()

        gem_res = sb.table("gemini_data").update({
            "untappd_url": new_u_url,
            "updated_at": now_iso
        }).eq("url", p_url).execute()

        logger.info(f"  Fixed: {item['name']}\n    -> New URL: {new_u_url}\n    -> {item['notes']}")

    # 2. Untappd データのスクレイピング・最新化
    logger.info(f"\n[2] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            upsert_res = sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('rating')} | Checkins: {details.get('rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(2.0)

    # 3. マテリアライズドビューのリフレッシュ
    logger.info("\n[3] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

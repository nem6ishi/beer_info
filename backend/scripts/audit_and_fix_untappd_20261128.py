"""
Batch Untappd audit & fix script for 2026-11-28.
Applies verified fixes from the daily beer enrichment & quality audit:
- 1 recent link corrected to exact batch (Inkhorn Mohua 2026 #2)
- 2 newly discovered unlinked beers scraped & linked (Traptoberfest, Hiruzen Vintage Ale V-8 2025)
- 2 rolling audit master Untappd records refreshed (Madame R. Galle, Yama-Bushi ume dark #001)
- 12 confirmed unlinked/ambiguous beers marked with updated untappd_enriched_at timestamp
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.core.utils import map_details_to_payload
from backend.src.services.untappd.http_client import close_async_client, scrape_beer_details

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

UNTAPPD_SCRAPE_URLS = [
    # Recent batch fix + Newly identified unlinked beers
    "https://untappd.com/b/inkhorn-brewing-mohua-2026-2/7700593",
    "https://untappd.com/b/trap-door-brewing-traptoberfest/7700824",
    "https://untappd.com/b/hiruzen-brewing-vintage-ale-v-8-2025/6521041",
    # Rolling audit refresh
    "https://untappd.com/b/fair-isle-madame-r-galle/3618004",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-ume-dark-001/6629682",
]

FIX_ITEMS = [
    # --- A. Recent 48h item batch correction (1) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=4298",
        "untappd_url": "https://untappd.com/b/inkhorn-brewing-mohua-2026-2/7700593",
        "gemini_update": {
            "brewery_name_en": "Inkhorn Brewing",
            "brewery_name_jp": "インクホーンブルーイング",
            "beer_name_en": "Mohua (2026 #2)",
            "beer_name_jp": "モフア 2026 #2",
            "beer_name_core": "Mohua (2026 #2)",
            "product_type": "beer",
            "is_set": False,
        },
    },
    # --- B. Newly discovered unlinked beers (2) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8351",
        "untappd_url": "https://untappd.com/b/trap-door-brewing-traptoberfest/7700824",
        "gemini_update": {
            "brewery_name_en": "Trap Door Brewing",
            "brewery_name_jp": "トラップドア",
            "beer_name_en": "TRAPTOBERFEST",
            "beer_name_jp": "トラップトバーフェスト",
            "beer_name_core": "TRAPTOBERFEST",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6855",
        "untappd_url": "https://untappd.com/b/hiruzen-brewing-vintage-ale-v-8-2025/6521041",
        "gemini_update": {
            "brewery_name_en": "Hiruzen Brewing",
            "brewery_name_jp": "蒜山醸造所つちとみず",
            "beer_name_en": "Vintage Ale V-8 (2025)",
            "beer_name_jp": "ヴィンテージエール 2025 [V-8]",
            "beer_name_core": "Vintage Ale V-8 (2025)",
            "product_type": "beer",
            "is_set": False,
        },
    },
]

# Confirmed unregistered or ambiguous (cannot determine hop/batch safely) -> touch untappd_enriched_at
INVESTIGATED_HOLD_URLS = [
    "https://witchcraftmarket.com/products/trinity-blaster-pale-ale",
    "https://witchcraftmarket.com/products/buchikamashi-helles",
    "https://www.arome.jp/products/detail.php?product_id=8431",
    "https://beer-chouseiya.shop/shopdetail/000000000860",
    "https://beer-chouseiya.shop/shopdetail/000000003442",
    "https://beer-chouseiya.shop/shopdetail/000000001311",
    "https://beer-chouseiya.shop/shopdetail/000000003451",
    "https://beer-chouseiya.shop/shopdetail/000000001597",
    "https://beer-chouseiya.shop/shopdetail/000000003468",
    "https://beervolta.com/?pid=173884556",
    "https://beer-chouseiya.shop/shopdetail/000000002921",
    "https://beer-chouseiya.shop/shopdetail/000000000108",
]


def run_db_op(op_func, max_retries=3, delay=1.0):
    for attempt in range(max_retries):
        try:
            return op_func()
        except Exception as e:
            logger.warning(f"DB op failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (attempt + 1))


async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("[1] Scraping and upserting Untappd master details...")
    for untappd_url in UNTAPPD_SCRAPE_URLS:
        details = await scrape_beer_details(untappd_url)
        if details and details.get("untappd_beer_name"):
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda p=payload: sync_execute(sb.table("untappd_data").upsert(p, on_conflict="untappd_url")))
            logger.info(f"  Upserted: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')}")
        else:
            logger.warning(f"  Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.4)

    await close_async_client()

    logger.info(f"[2] Updating {len(FIX_ITEMS)} linked items in gemini_data and scraped_beers...")
    for item in FIX_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])
        gem_update["url"] = url
        gem_update["untappd_url"] = untappd_url
        gem_update["updated_at"] = now_iso

        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))
        run_db_op(
            lambda u=url, uu=untappd_url: sync_execute(
                sb.table("scraped_beers")
                .update({"untappd_url": uu, "untappd_enriched_at": now_iso})
                .eq("url", u)
            )
        )
        logger.info(f"  Updated {url} -> {untappd_url}")

    logger.info(f"[3] Recording investigation timestamp on {len(INVESTIGATED_HOLD_URLS)} hold/unregistered beers...")
    for url in INVESTIGATED_HOLD_URLS:
        run_db_op(
            lambda u=url: sync_execute(
                sb.table("scraped_beers")
                .update({"untappd_enriched_at": now_iso})
                .eq("url", u)
            )
        )
        logger.info(f"  Marked investigated: {url}")

    logger.info("[4] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())

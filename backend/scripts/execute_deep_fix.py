import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.services.untappd.db_queries import upsert_untappd_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPECIFIC_FIXES = [
    {
        "shop": "アローム",
        "name_kw": "ドライホップド・ブレットサワー・ヴィンテージ2023",
        "new_url": "https://untappd.com/b/ajb-co-brett-sour/6287680"
    },
    {
        "shop": "BEER VOLTA",
        "name_kw": "ウェストコーストIPA イズ デッド",
        "new_url": "https://untappd.com/b/cloudwater-brew-co-west-coast-ipa-is-dead-2026/7518474"
    },
    {
        "shop": "BEER VOLTA",
        "name_kw": "タイム アフター タイム",
        "new_url": "https://untappd.com/b/dd4d-brewing-time-after-thyme/6830991"
    },
    {
        "shop": "WITCH CRAFT MARKET",
        "name_kw": "Liquid hoppiness",
        "new_url": "https://untappd.com/b/sierra-nevada-brewing-co-liquid-hoppiness-juicy-ipa/4932935"
    }
]

# Severely corrupted URLs on sold out beers that should be cleared
URLS_TO_CLEAR = [
    "https://untappd.com/b/homebrew-modern-times-blazing-world-clone/1183543",
    "https://untappd.com/b/oxbow-brewing-company-northern-lager/3631172",
    "https://untappd.com/b/founders-brewing-co-bottle-shop-series-nemesis/6951",
    "https://untappd.com/b/dogfish-head-craft-brewery-60-minute-ipa-2025/6263470",
    "https://untappd.com/b/adroit-theory-what-evil-lurks-ghost-901/3984458",
    "https://untappd.com/b/vertere-unlearn/5124745",
    "https://untappd.com/b/tamamura-honten-co-yama-bushi-hop-and-brett/1649979",
    "https://untappd.com/b/burial-beer-co-liminal-space/5926515",
    "https://untappd.com/b/hop-butcher-for-the-world-halogen-farm/3204364",
    "https://untappd.com/b/two-rabbits-brewing-company-bourbon-scotch-ale/4716503",
    "https://untappd.com/b/green-flash-brewing-company-saturhaze/3188097"
]

async def main():
    supabase = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    def parse_float(val):
        if val is None:
            return None
        try:
            return float(str(val).replace(",", "").replace("%", "").strip())
        except Exception:
            return None

    # 1. Scrape & upsert new URLs
    unique_urls = list(set(f["new_url"] for f in SPECIFIC_FIXES))
    for url in unique_urls:
        logger.info(f"Scraping {url}...")
        details = await scrape_beer_details(url)
        if not details:
            logger.error(f"Failed to scrape {url}!")
            continue

        payload = {
            "untappd_url": url,
            "beer_name": details.get("untappd_beer_name"),
            "brewery_name": details.get("untappd_brewery_name"),
            "style": details.get("untappd_style"),
            "abv": details.get("untappd_abv"),
            "ibu": details.get("untappd_ibu"),
            "rating": str(details.get("untappd_rating")) if details.get("untappd_rating") is not None else None,
            "rating_count": str(details.get("untappd_rating_count")) if details.get("untappd_rating_count") is not None else None,
            "image_url": details.get("untappd_label"),
            "untappd_brewery_url": details.get("untappd_brewery_url"),
            "abv_num": parse_float(details.get("untappd_abv")),
            "ibu_num": parse_float(details.get("untappd_ibu")),
            "rating_num": parse_float(details.get("untappd_rating")),
            "rating_count_num": parse_float(details.get("untappd_rating_count")),
            "fetched_at": now_iso
        }
        upsert_untappd_data(supabase, [payload])
        logger.info(f"Upserted {payload['brewery_name']} - {payload['beer_name']} ({payload['rating_num']})")

    # 2. Update specific scraped_beers
    for f in SPECIFIC_FIXES:
        res = supabase.table("scraped_beers")\
            .select("url, name, shop")\
            .eq("shop", f["shop"])\
            .ilike("name", f"%{f['name_kw']}%")\
            .execute()
        for item in res.data:
            logger.info(f"Fixing [{item['shop']}] {item['name']} -> {f['new_url']}")
            supabase.table("scraped_beers").update({
                "untappd_url": f["new_url"],
                "untappd_enriched_at": now_iso
            }).eq("url", item["url"]).execute()

    # 3. Clear severely corrupted URLs from scraped_beers
    for bad_url in URLS_TO_CLEAR:
        res = supabase.table("scraped_beers")\
            .select("url, name, shop")\
            .eq("untappd_url", bad_url)\
            .execute()
        if res.data:
            logger.info(f"Clearing {len(res.data)} items linked to corrupted URL {bad_url}...")
            for item in res.data:
                supabase.table("scraped_beers").update({
                    "untappd_url": None,
                    "untappd_enriched_at": None
                }).eq("url", item["url"]).execute()

    # 4. Refresh materialized view
    logger.info("Refreshing materialized view...")
    refresh_materialized_view(supabase, logger)
    logger.info("Successfully completed deep fix and view refresh!")

if __name__ == '__main__':
    asyncio.run(main())

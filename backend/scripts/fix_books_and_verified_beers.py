import asyncio
import logging
from datetime import datetime
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 書籍・非ビールの誤判定修正
BOOK_TITLES = [
    "日本のクラフトビールのすべて",
    "ビールの放課後 臨時増刊号",
    "ビールの放課後 第5号",
    "ビールの放課後 第6巻",
    "増補版　ビールの放課後　第7号",
    "ビールの放課後 創刊号+有明本"
]

# 2. 個別判明した実在ビールの手動連携
SPECIFIC_BEER_UPDATES = [
    {
        "url": "https://151l.shop/?pid=189524945", # ザ ヴェイル オールドサン
        "untappd_url": "https://untappd.com/b/the-veil-brewing-co-old-sun-w-raspberries-and-blackberries/4082902",
        "gemini_update": {
            "brewery_name_en": "The Veil Brewing Co.",
            "brewery_name_jp": "ヴェイル",
            "beer_name_en": "Old Sun (w/ Raspberries & Blackberries)",
            "beer_name_core": "Old Sun",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/the-veil-brewing-co-old-sun-w-raspberries-and-blackberries/4082902"
        }
    },
    {
        "url": "https://beervolta.com/?pid=193132039", # Revision DIPA
        "untappd_url": "https://untappd.com/b/revision-brewing-company-dipa/2008435",
        "gemini_update": {
            "brewery_name_en": "Revision Brewing Company",
            "brewery_name_jp": "リビジョン",
            "beer_name_en": "DIPA",
            "beer_name_core": "DIPA",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/revision-brewing-company-dipa/2008435"
        }
    },
    {
        "url": "https://beervolta.com/?pid=192804561", # Baghaven Granadilla
        "untappd_url": "https://untappd.com/b/baghaven-brewing-and-blending-granadilla-blend-1/2569819",
        "gemini_update": {
            "brewery_name_en": "Baghaven Brewing and Blending",
            "brewery_name_jp": "ミッケラー バウヘブン",
            "beer_name_en": "Granadilla Blend 1",
            "beer_name_core": "Granadilla",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/baghaven-brewing-and-blending-granadilla-blend-1/2569819"
        }
    },
    {
        "url": "https://151l.shop/?pid=193571616", # Tarantula hill Dazzle Berry
        "untappd_url": "https://untappd.com/b/tarantula-hill-brewing-co-razzle-dazzle-raspberry-and-blackberry/4307112",
        "gemini_update": {
            "brewery_name_en": "Tarantula Hill Brewing Co.",
            "brewery_name_jp": "タランチュラヒル",
            "beer_name_en": "Dazzle Berry Sour (Raspberry & Blackberry)",
            "beer_name_core": "Dazzle Berry",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/tarantula-hill-brewing-co-razzle-dazzle-raspberry-and-blackberry/4307112"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001777", # 琥珀ヴァイツェン / 大山ビール
        "untappd_url": "https://untappd.com/b/daisen-g-beer-daisen-g-amber-weiss/1817866",
        "gemini_update": {
            "brewery_name_en": "Kumezakura Daisen Brewery",
            "brewery_name_jp": "大山Gビール",
            "beer_name_en": "Daisen G Amber Weiss",
            "beer_name_core": "Amber Weiss",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/daisen-g-beer-daisen-g-amber-weiss/1817866"
        }
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.utcnow().isoformat()

    # 1. 書籍の誤判定修正
    logger.info("=== Fixing misclassified books ===")
    for title_kw in BOOK_TITLES:
        b_res = sb.table("scraped_beers").select("url, name").ilike("name", f"%{title_kw}%").execute()
        for b in b_res.data:
            url = b["url"]
            up_res = sb.table("gemini_data").update({"product_type": "other"}).eq("url", url).execute()
            logger.info(f"  Fixed product_type -> 'other': [{b['name']}] (Updated: {len(up_res.data)} rows)")

    # 2. 実在ビールの個別連携
    logger.info("\n=== Linking specific verified beers ===")
    for item in SPECIFIC_BEER_UPDATES:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"\nProcessing: {url} -> {untappd_url}")
        
        # gemini_data
        sb.table("gemini_data").update(gem_update).eq("url", url).execute()
        # scraped_beers
        sb.table("scraped_beers").update({"untappd_url": untappd_url}).eq("url", url).execute()
        # untappd_search_failures
        sb.table("untappd_search_failures").update({
            "resolved": True,
            "resolved_at": now_iso,
            "notes": "Verified and resolved in batch inspection"
        }).eq("product_url", url).execute()

        # untappd_data
        existing_unt = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute().data
        if not existing_unt:
            logger.info(f"  Scraping details for {untappd_url}...")
            details = await scrape_beer_details(untappd_url)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = untappd_url
                payload["fetched_at"] = now_iso
                sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                logger.info(f"  Upserted details for: {details.get('untappd_beer_name')}")
            await asyncio.sleep(2)
        else:
            logger.info(f"  Details already exist in untappd_data")

    # 3. リフレッシュ
    logger.info("\nRefreshing materialized view...")
    refresh_materialized_view(sb, logger)
    logger.info("Done!")

if __name__ == "__main__":
    asyncio.run(main())

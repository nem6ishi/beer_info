import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 誤紐付け是正 (6件)
FIX_MISASSIGNED_ITEMS = [
    {
        # ちょうせいや「すもものきもち」が赤ぶどうのエール(148312)に誤紐付けされていたため Sumomo Ale(7676492) へ是正
        "url": "https://beer-chouseiya.shop/shopdetail/000000003460",
        "untappd_url": "https://untappd.com/b/ikspiari-co-sumomo-ale/7676492",
        "gemini_update": {
            "brewery_name_en": "IKSPIARI Co.",
            "brewery_name_jp": "ハーヴェスト・ムーン",
            "beer_name_en": "Sumomo Ale",
            "beer_name_jp": "すもものきもち",
            "beer_name_core": "Sumomo Ale",
            "search_hint": "Sumomo Ale IKSPIARI Harvest Moon",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ikspiari-co-sumomo-ale/7676492",
        },
    },
    {
        # ちょうせいや「米麦マリアージュ」が Harvestmoon Pale Ale(98597) に誤紐付けされていたため Beibaku Mariage(989619) へ是正
        "url": "https://beer-chouseiya.shop/shopdetail/000000003459",
        "untappd_url": "https://untappd.com/b/ikspiari-co-harvestmoon-beibaku-mariage/989619",
        "gemini_update": {
            "brewery_name_en": "IKSPIARI Co.",
            "brewery_name_jp": "ハーヴェスト・ムーン",
            "beer_name_en": "Harvestmoon Beibaku Mariage",
            "beer_name_jp": "米麦マリアージュ",
            "beer_name_core": "Beibaku Mariage",
            "search_hint": "Harvestmoon Beibaku Mariage IKSPIARI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ikspiari-co-harvestmoon-beibaku-mariage/989619",
        },
    },
    {
        # アローム「玉村本店 / 木樽熟成 山伏 blonde #7」が #006(6449855) に誤紐付けされていたため #007(6961953) へ是正
        "url": "https://www.arome.jp/products/detail.php?product_id=6451",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-blonde-007/6961953",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "玉村本店",
            "beer_name_en": "Barrel Aged Yama-Bushi blonde #007",
            "beer_name_jp": "木樽熟成 山伏 blonde #7",
            "beer_name_core": "Barrel Aged Yama-Bushi blonde #007",
            "search_hint": "Barrel Aged Yama-Bushi blonde 007 Tamamura Honten",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-blonde-007/6961953",
        },
    },
    {
        # BEER VOLTA「Kemker Aoltbeer 07-2022 Plums」が無印 Aoltbeer(2570157) に紐づいていたため Plums(5286669) へ是正
        "url": "https://beervolta.com/?pid=178213496",
        "untappd_url": "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-aoltbeer-2022-07-plums/5286669",
        "gemini_update": {
            "brewery_name_en": "Kemker Kultuur (Brauerei J. Kemker)",
            "brewery_name_jp": "ケムカー",
            "beer_name_en": "Aoltbeer (2022-07) Plums",
            "beer_name_jp": "アルトビア 07-2022 プラムズ",
            "beer_name_core": "Aoltbeer (2022-07) Plums",
            "search_hint": "Aoltbeer 2022-07 Plums Kemker",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-aoltbeer-2022-07-plums/5286669",
        },
    },
    {
        # アローム「蒜山醸造所つちとみず / ヴィンテージエール 2025 [V-8]」が V-1 (2024)(5855395) に誤紐付けされていたため解除 (Untappd未登録)
        "url": "https://www.arome.jp/products/detail.php?product_id=6855",
        "untappd_url": None,
        "gemini_update": {
            "brewery_name_en": "Hiruzen Brewing",
            "brewery_name_jp": "蒜山醸造所つちとみず",
            "beer_name_en": "Vintage Ale 2025 [V-8]",
            "beer_name_jp": "ヴィンテージエール 2025 [V-8]",
            "beer_name_core": "Vintage Ale V-8 (2025)",
            "search_hint": "Vintage Ale V-8 2025 Hiruzen Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None,
        },
    },
    {
        # ちょうせいや「インペリアルスタウト 2025/大山Gビール」が (2023)(6539237) に誤紐付けされていたため解除 (2025年版 Untappd未登録)
        "url": "https://beer-chouseiya.shop/shopdetail/000000000108",
        "untappd_url": None,
        "gemini_update": {
            "brewery_name_en": "Kumezakura Daisen Brewery",
            "brewery_name_jp": "大山Gビール",
            "beer_name_en": "Daisen G Imperial Stout (2025)",
            "beer_name_jp": "インペリアルスタウト 2025",
            "beer_name_core": "Daisen G Imperial Stout 2025",
            "search_hint": "Daisen G Imperial Stout 2025 Kumezakura",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None,
        },
    },
]

# 2. 横展開 (BEER VOLTA の Lyric 3件)
CROSS_STORE_ENRICH_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=194573869",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Fear Addicted (2026)",
            "beer_name_jp": "フィアー アディクテッド 2026",
            "beer_name_core": "Fear Addicted",
            "search_hint": "Fear Addicted 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573868",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Familiar Heroes (2026)",
            "beer_name_jp": "ファミリア ヒーローズ",
            "beer_name_core": "Familiar Heroes",
            "search_hint": "Familiar Heroes 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-familiar-heroes-2026/7223006",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573870",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Death Greets Me Warm",
            "beer_name_jp": "デス グリーツ ミー ウォーム",
            "beer_name_core": "Death Greets Me Warm",
            "search_hint": "Death Greets Me Warm Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8420",
        "untappd_url": "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
        "gemini_update": {
            "brewery_name_en": "Off Script Brewing",
            "brewery_name_jp": "オフスクリプト",
            "beer_name_en": "Yeah, Science!",
            "beer_name_jp": "イェー、サイエンス！",
            "beer_name_core": "Yeah, Science!",
            "search_hint": "Yeah, Science! Off Script Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573865",
        "untappd_url": "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
        "gemini_update": {
            "brewery_name_en": "Off Script Brewing",
            "brewery_name_jp": "オフスクリプト",
            "beer_name_en": "Yeah, Science!",
            "beer_name_jp": "イェー サイエンス",
            "beer_name_core": "Yeah, Science!",
            "search_hint": "Yeah, Science! Off Script Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/off-script-brewing-yeah-science/7161772",
        },
    },
]

UNTAPPD_SCRAPE_URLS = [
    "https://untappd.com/b/ikspiari-co-sumomo-ale/7676492",
    "https://untappd.com/b/ikspiari-co-harvestmoon-beibaku-mariage/989619",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-blonde-007/6961953",
    "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-aoltbeer-2022-07-plums/5286669",
]


def run_db_op(op_func, max_retries=3, delay=1.0):
    for attempt in range(max_retries):
        try:
            return op_func()
        except Exception as e:
            logger.warning(f"DB operation failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise e
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
        await asyncio.sleep(0.5)

    await close_async_client()

    all_items = FIX_MISASSIGNED_ITEMS + CROSS_STORE_ENRICH_ITEMS
    logger.info(f"\n[2] Updating {len(all_items)} items in gemini_data and scraped_beers...")
    for item in all_items:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])
        gem_update["url"] = url
        gem_update["updated_at"] = now_iso

        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))
        run_db_op(lambda u=url, uu=untappd_url: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": uu,
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))
        logger.info(f"  Updated {url} -> {untappd_url}")

    logger.info("\n[3] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("Materialized view refreshed successfully!")


if __name__ == "__main__":
    asyncio.run(main())

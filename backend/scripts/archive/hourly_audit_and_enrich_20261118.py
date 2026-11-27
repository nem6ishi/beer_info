import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 未エンリッチ商品 (最優先)
NEW_ENRICH_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=185003639",
        "name": "エブリウェア エブリシングオールウェイズ / everywhere everything always",
        "untappd_url": "https://untappd.com/b/everywhere-everything-always/5138836",
        "gemini_update": {
            "brewery_name_en": "everywhere",
            "brewery_name_jp": "エブリウェア",
            "beer_name_en": "everything always",
            "beer_name_jp": "エブリシング オールウェイズ",
            "beer_name_core": "everything always",
            "search_hint": "everything always everywhere",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/everywhere-everything-always/5138836",
        },
    },
    # Untappd未紐付け在庫ビール (特定済み登録)
    {
        "url": "https://beervolta.com/?pid=173883590",
        "name": "サイドプロジェクト x ザ ブルールーテルー / Side Project x The Bruery Terreux Mousseux Alban",
        "untappd_url": "https://untappd.com/b/side-project-brewing-mousseux-alban/3676627",
        "gemini_update": {
            "brewery_name_en": "Side Project Brewing",
            "brewery_name_jp": "サイドプロジェクト",
            "beer_name_en": "Mousseux Alban",
            "beer_name_jp": "ムスー アルバン",
            "beer_name_core": "Mousseux Alban",
            "search_hint": "Mousseux Alban Side Project Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/side-project-brewing-mousseux-alban/3676627",
        },
    },
    {
        "url": "https://beervolta.com/?pid=186281357",
        "name": "ペンドルイド スポンティニアスチェリーズ / Pen Druid Spontaneous Cherries",
        "untappd_url": "https://untappd.com/b/pen-druid-brewing-spontaneous-cherries/4465475",
        "gemini_update": {
            "brewery_name_en": "Pen Druid Brewing",
            "brewery_name_jp": "ペンドルイド",
            "beer_name_en": "Spontaneous Cherries",
            "beer_name_jp": "スポンティニアス チェリーズ",
            "beer_name_core": "Spontaneous Cherries",
            "search_hint": "Spontaneous Cherries Pen Druid Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/pen-druid-brewing-spontaneous-cherries/4465475",
        },
    },
    {
        "url": "https://beervolta.com/?pid=185148490",
        "name": "フィフティフィフティ エクリプス2024 - ブラックマンハッタン / FiftyFifty Eclipse 2024 - Black Manhattan",
        "untappd_url": "https://untappd.com/b/fiftyfifty-brewing-co-black-manhattan-blend-eclipse-2024/6084312",
        "gemini_update": {
            "brewery_name_en": "FiftyFifty Brewing Co.",
            "brewery_name_jp": "フィフティフィフティ",
            "beer_name_en": "Black Manhattan Blend Eclipse (2024)",
            "beer_name_jp": "エクリプス2024 ブラックマンハッタン",
            "beer_name_core": "Black Manhattan Blend Eclipse",
            "search_hint": "Black Manhattan Blend Eclipse 2024 FiftyFifty Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fiftyfifty-brewing-co-black-manhattan-blend-eclipse-2024/6084312",
        },
    },
    {
        "url": "https://beervolta.com/?pid=186935165",
        "name": "ケムカー アルトビア no.02-2024 リースリング / Kemker Aoltbeer no. 02-2024 “Riesling” 750ml",
        "untappd_url": "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-konigin-der-reben-2021/6212747",
        "gemini_update": {
            "brewery_name_en": "Kemker Kultuur (Brauerei J. Kemker)",
            "brewery_name_jp": "ケムカー クルトゥール",
            "beer_name_en": "Königin Der Reben 2021",
            "beer_name_jp": "アルトビア no.02-2024 リースリング",
            "beer_name_core": "Königin Der Reben 2021",
            "search_hint": "Königin Der Reben 2021 Kemker Kultuur Aoltbeer 02-2024 Riesling",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-konigin-der-reben-2021/6212747",
        },
    },
    {
        "url": "https://beervolta.com/?pid=178214079",
        "name": "ボエレネルフ エイレンボッシュ / Het Boerenerf Eylenbosch Gueuze 2023-1",
        "untappd_url": "https://untappd.com/b/boerenerf-bottle-oude-gueuze-2023-1/5396233",
        "gemini_update": {
            "brewery_name_en": "Boerenerf",
            "brewery_name_jp": "ボエレネルフ エイレンボッシュ",
            "beer_name_en": "Oude Gueuze (2023-1)",
            "beer_name_jp": "エイレンボッシュ オードグーズ 2023-1",
            "beer_name_core": "Oude Gueuze (2023-1)",
            "search_hint": "Oude Gueuze 2023-1 Boerenerf Eylenbosch",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/boerenerf-bottle-oude-gueuze-2023-1/5396233",
        },
    },
]

# 2. 直近追加 & ローリング監査 誤紐付け・メタデータ是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003453",
        "name": "【DUBLIN STOUT/箕面ビール】",
        "untappd_url": "https://untappd.com/b/minoh-beer-minoh-beer/7682935",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "DUBLIN STOUT",
            "beer_name_jp": "ダブリンスタウト",
            "beer_name_core": "DUBLIN STOUT",
            "search_hint": "DUBLIN STOUT Minoh Beer WHC Lab",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-minoh-beer/7682935",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000269",
        "name": "【スタウト/箕面ビール】",
        "untappd_url": "https://untappd.com/b/minoh-beer-minoh-stout/22927",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Minoh Stout",
            "beer_name_jp": "スタウト",
            "beer_name_core": "Minoh Stout",
            "search_hint": "Minoh Stout Minoh Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-minoh-stout/22927",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000270",
        "name": "【ヴァイツェン/箕面ビール】",
        "untappd_url": "https://untappd.com/b/minoh-beer-minoh-weizen/88214",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Minoh Weizen",
            "beer_name_jp": "ヴァイツェン",
            "beer_name_core": "Minoh Weizen",
            "search_hint": "Minoh Weizen Minoh Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-minoh-weizen/88214",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001123",
        "name": "【ペールエール/箕面ビール】",
        "untappd_url": "https://untappd.com/b/minoh-beer-pale-ale/62766",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Pale Ale",
            "beer_name_jp": "ペールエール",
            "beer_name_core": "Pale Ale",
            "search_hint": "Pale Ale Minoh Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-pale-ale/62766",
        },
    },
    {
        "url": "https://witchcraftmarket.com/products/lupulin-riot",
        "name": "[Revision] Lupulin Riot / ルプリン ライオット",
        "untappd_url": "https://untappd.com/b/revision-brewing-company-lupulin-riot/6781485",
        "gemini_update": {
            "brewery_name_en": "Revision Brewing Company",
            "brewery_name_jp": "リビジョン ブルーイング",
            "beer_name_en": "Lupulin Riot",
            "beer_name_jp": "ルプリン ライオット",
            "beer_name_core": "Lupulin Riot",
            "search_hint": "Lupulin Riot Revision Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/revision-brewing-company-lupulin-riot/6781485",
        },
    },
]

# 3. Untappd詳細取得・最新化対象 (新規・是正・ローリング対象)
BEER_REFRESH_URLS = [
    # 新規エンリッチ & 未紐付け特定
    "https://untappd.com/b/everywhere-everything-always/5138836",
    "https://untappd.com/b/side-project-brewing-mousseux-alban/3676627",
    "https://untappd.com/b/pen-druid-brewing-spontaneous-cherries/4465475",
    "https://untappd.com/b/fiftyfifty-brewing-co-black-manhattan-blend-eclipse-2024/6084312",
    "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-konigin-der-reben-2021/6212747",
    "https://untappd.com/b/boerenerf-bottle-oude-gueuze-2023-1/5396233",
    # 是正対象
    "https://untappd.com/b/minoh-beer-minoh-beer/7682935",
    "https://untappd.com/b/minoh-beer-minoh-stout/22927",
    "https://untappd.com/b/minoh-beer-minoh-weizen/88214",
    "https://untappd.com/b/minoh-beer-pale-ale/62766",
    # ローリング巡回監査
    "https://untappd.com/b/revision-brewing-company-lupulin-riot/6781485",
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

    # 1. 誤紐付け・メタデータ是正
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned/mismatched beer items...")
    for item in FIX_MISASSIGNED_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])

        logger.info(f"  Fixing {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso,
        }).eq("url", url)))

    # 2. 新規・未紐付け特定商品のエンリッチ登録
    logger.info(f"\n[2] Enriching {len(NEW_ENRICH_ITEMS)} newly identified beer items...")
    for item in NEW_ENRICH_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])

        logger.info(f"  Enriching {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso,
        }).eq("url", url)))

    # 3. Untappd データの詳細取得・最新化
    logger.info(f"\n[3] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            logger.info(
                f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} "
                f"| Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}"
            )
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.5)

    await close_async_client()

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 誤紐付け修正対象
FIX_MISMATCH_ITEMS = [
    {
        "url": "https://151l.shop/?pid=189287479",
        "name": "バーバー　キャンディバア　ブルーベリークランベリーピスタチオチョコレート　空輸（BaaBaa Brewhouse Candy Baa）",
        "old_untappd_url": "https://untappd.com/b/baa-baa-brewhouse-candy-baa-triple-berry-mango-chocolate/4323233",
        "new_untappd_url": "https://untappd.com/b/baa-baa-brewhouse-candy-baa-blueberry-cranberry-chocolate-and-pistachio/4344191",
        "gemini_update": {
            "brewery_name_en": "Baa Baa Brewhouse",
            "brewery_name_jp": "バーバー",
            "beer_name_en": "Candy Baa - Blueberry, Cranberry, Chocolate & Pistachio",
            "beer_name_jp": "キャンディバア ブルーベリー クランベリー チョコレート & ピスタチオ",
            "beer_name_core": "Candy Baa Blueberry Cranberry Chocolate & Pistachio",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/baa-baa-brewhouse-candy-baa-blueberry-cranberry-chocolate-and-pistachio/4344191"
        }
    },
    {
        "url": "https://151l.shop/?pid=176171481",
        "name": "アンカレッジ　ウェンディゴ（Anchorage Brewing Co Wendigo）",
        "old_untappd_url": "https://untappd.com/b/anchorage-brewing-company-wendigo-triple-oaked-batch-3-2024/5908944",
        "new_untappd_url": "https://untappd.com/b/anchorage-brewing-company-wendigo-triple-oaked-batch-2-2023/5379452",
        "gemini_update": {
            "brewery_name_en": "Anchorage Brewing Company",
            "brewery_name_jp": "アンカレッジ",
            "beer_name_en": "Wendigo - Triple Oaked (Batch 2 - 2023)",
            "beer_name_jp": "ウェンディゴ トリプルオークド (バッチ2 - 2023)",
            "beer_name_core": "Wendigo Triple Oaked",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/anchorage-brewing-company-wendigo-triple-oaked-batch-2-2023/5379452"
        }
    }
]

# 2. 新規エンリッチ & Untappd特定済み商品の登録
NEW_ENRICH_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/sonar-tune",
        "name": "[AMAKUSA SONAR BEER] SONAR TUNE/ ソナーチューン",
        "untappd_url": "https://untappd.com/b/kumamoto-craft-beer-company-sonar-tune/7659113",
        "gemini_update": {
            "brewery_name_en": "AMAKUSA SONAR BEER",
            "brewery_name_jp": "天草ソナービール",
            "beer_name_en": "Sonar Tune",
            "beer_name_jp": "ソナーチューン",
            "beer_name_core": "Sonar Tune",
            "search_hint": "Sonar Tune Kumamoto Craft Beer Company AMAKUSA SONAR BEER",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kumamoto-craft-beer-company-sonar-tune/7659113"
        }
    }
]

# 3. Untappd未登録商品の監査確認更新（次回以降の巡回間隔調整）
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6226",
        "name": "玉村本店 / 木樽熟成 山伏 b3 miyama #004 (Barrel Aged Farmhouse Ale) 750ml瓶",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten",
            "brewery_name_jp": "玉村本店",
            "beer_name_en": "Barrel Aged Yama-Bushi b3 miyama #004",
            "beer_name_jp": "木樽熟成 山伏 b3 miyama #004",
            "beer_name_core": "Barrel Aged Yama-Bushi b3 miyama",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/trinity-blaster-pale-ale",
        "name": "[GAME BREW] 魔龍公 ビューネイ TRINITY BLASTER PALE ALE / トリニティー ブラスター ペールエール",
        "gemini_update": {
            "brewery_name_en": "Game Brew",
            "brewery_name_jp": "ゲームブリュー",
            "beer_name_en": "Trinity Blaster Pale Ale",
            "beer_name_jp": "魔龍公 ビューネイ トリニティー ブラスター ペールエール",
            "beer_name_core": "Trinity Blaster Pale Ale",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8294",
        "name": "トートピアブルワリー / 4フォビア-濁- (4恐怖症) (2x Mash TDH Hazy TIPA) 500ml缶",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia - Nigo",
            "beer_name_jp": "4フォビア -濁-",
            "beer_name_core": "4phobia Nigo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003441",
        "name": "【4phobia-濁-/Totopia】",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia - Nigo",
            "beer_name_jp": "4フォビア -濁-",
            "beer_name_core": "4phobia Nigo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    }
]

# 4. ローリング巡回・Untappd詳細取得＆更新対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/popihn-sauvages-assemblage-3-2021/4677676",
    "https://untappd.com/b/hudson-valley-brewery-pastel/5074083",
    "https://untappd.com/b/firestone-walker-brewing-company-pivo-pils/74539"
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

    # 1. 誤紐付け修正
    logger.info(f"\n[1] Correcting {len(FIX_MISMATCH_ITEMS)} mismatched beer items...")
    for item in FIX_MISMATCH_ITEMS:
        url = item["url"]
        new_untappd_url = item["new_untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"  Fixing {url}\n    Old: {item['old_untappd_url']}\n    New: {new_untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": new_untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url)))

        details = await scrape_beer_details(new_untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = new_untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            logger.info(f"  ✅ Fixed & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {new_untappd_url}")
        await asyncio.sleep(0.5)

    # 2. 新規特定商品のエンリッチ登録
    logger.info(f"\n[2] Enriching {len(NEW_ENRICH_ITEMS)} newly identified beer items...")
    for item in NEW_ENRICH_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"  Enriching {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url)))

        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 3. 未登録ビールの監査日時更新
    logger.info(f"\n[3] Marking {len(UNREGISTERED_BEER_ITEMS)} unregistered items as audited...")
    for item in UNREGISTERED_BEER_ITEMS:
        url = item["url"]
        gem_update = item["gemini_update"]
        logger.info(f"  Audited unregistered item: {item['name']}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", url)))

    # 4. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[4] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 5. マテリアライズドビューのリフレッシュ
    logger.info("\n[5] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

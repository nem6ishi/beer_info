import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. ヴィンテージ誤紐付け是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=405",
        "name": "デ カム / 2018 トロス ベッセン 750ml瓶 [De Cam / Tros Bessen]",
        "untappd_url": "https://untappd.com/b/geuzestekerij-de-cam-trosbessen-2018/2629281",
        "gemini_update": {
            "brewery_name_en": "Geuzestekerij De Cam",
            "brewery_name_jp": "デ カム",
            "beer_name_en": "Trosbessen (2018)",
            "beer_name_jp": "トロス ベッセン 2018",
            "beer_name_core": "Trosbessen",
            "search_hint": "Trosbessen 2018 Geuzestekerij De Cam",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/geuzestekerij-de-cam-trosbessen-2018/2629281"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=648",
        "name": "BFM / 2018 アベイ・ドゥ・サン・ボンシェン (Bière de Garde) 750ml瓶 [BFM / Abbaye de Saint Bon-Chien]",
        "untappd_url": "https://untappd.com/b/brasserie-des-franches-montagnes-bfm-abbaye-de-saint-bon-chien-2018/2946234",
        "gemini_update": {
            "brewery_name_en": "Brasserie des Franches-Montagnes (BFM)",
            "brewery_name_jp": "BFM",
            "beer_name_en": "Abbaye de Saint Bon-Chien (2018)",
            "beer_name_jp": "アベイ ドゥ サン ボンシェン 2018",
            "beer_name_core": "Abbaye de Saint Bon-Chien",
            "search_hint": "Abbaye de Saint Bon-Chien 2018 Brasserie des Franches-Montagnes BFM",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brasserie-des-franches-montagnes-bfm-abbaye-de-saint-bon-chien-2018/2946234"
        }
    }
]

# 2. 新規エンリッチ & Untappd特定済み商品の登録
NEW_ENRICH_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=174204114",
        "name": "ボエレネルフ エイレンボッシュ オード クリーク / Het Boerenerf Eylenbosch Oude Kriek (Oogst 2020)",
        "untappd_url": "https://untappd.com/b/het-boerenerf-eylenbosch-oude-kriek-oogst-2020/4366733",
        "gemini_update": {
            "brewery_name_en": "Het Boerenerf",
            "brewery_name_jp": "ボエレネルフ エイレンボッシュ",
            "beer_name_en": "Eylenbosch Oude Kriek (Oogst 2020)",
            "beer_name_jp": "エイレンボッシュ オード クリーク (Oogst 2020)",
            "beer_name_core": "Oude Kriek",
            "search_hint": "Het Boerenerf Eylenbosch Oude Kriek Oogst 2020",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/het-boerenerf-eylenbosch-oude-kriek-oogst-2020/4366733"
        }
    },
    {
        "url": "https://beervolta.com/?pid=174204138",
        "name": "ボエレネルフ エイレンボッシュ / Het Boerenerf Eylenbosch Kers • Kaneel (Oogst 2021)",
        "untappd_url": "https://untappd.com/b/het-boerenerf-eylenbosch-kers-kaneel-oogst-2021/4802153",
        "gemini_update": {
            "brewery_name_en": "Het Boerenerf",
            "brewery_name_jp": "ボエレネルフ エイレンボッシュ",
            "beer_name_en": "Eylenbosch Kers • Kaneel (Oogst 2021)",
            "beer_name_jp": "エイレンボッシュ ケルス カネル (Oogst 2021)",
            "beer_name_core": "Kers • Kaneel",
            "search_hint": "Het Boerenerf Eylenbosch Kers Kaneel Oogst 2021",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/het-boerenerf-eylenbosch-kers-kaneel-oogst-2021/4802153"
        }
    },
    {
        "url": "https://beervolta.com/?pid=178462230",
        "name": "ワイルドフラワー グッド アズ ゴールド / Wildflower Good As Gold (Blend #18)",
        "untappd_url": "https://untappd.com/b/wildflower-brewing-and-blending-good-as-gold/2830809",
        "gemini_update": {
            "brewery_name_en": "Wildflower Brewing & Blending",
            "brewery_name_jp": "ワイルドフラワー",
            "beer_name_en": "Good As Gold",
            "beer_name_jp": "グッド アズ ゴールド",
            "beer_name_core": "Good As Gold",
            "search_hint": "Good As Gold Wildflower Brewing and Blending",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/wildflower-brewing-and-blending-good-as-gold/2830809"
        }
    },
    {
        "url": "https://beervolta.com/?pid=178382660",
        "name": "ティルカン オードルバーブティルカンアランシエンヌ / Tilquin Oude Rhubarbe Tilquin a l'Ancienne 375ml",
        "untappd_url": "https://untappd.com/b/gueuzerie-tilquin-oude-rhubarbe-tilquin-a-l-ancienne-2021-2022/4788026",
        "gemini_update": {
            "brewery_name_en": "Gueuzerie Tilquin",
            "brewery_name_jp": "ティルカン",
            "beer_name_en": "Oude Rhubarbe Tilquin à l'Ancienne",
            "beer_name_jp": "オード ルバーブ ティルカン ア ランシエンヌ",
            "beer_name_core": "Oude Rhubarbe Tilquin à l'Ancienne",
            "search_hint": "Oude Rhubarbe Tilquin a l'Ancienne Gueuzerie Tilquin",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/gueuzerie-tilquin-oude-rhubarbe-tilquin-a-l-ancienne-2021-2022/4788026"
        }
    },
    {
        "url": "https://beervolta.com/?pid=178384066",
        "name": "ティルカン オードルバーブティルカンアランシエンヌ / Tilquin Oude Rhubarbe Tilquin a l'Ancienne 750ml",
        "untappd_url": "https://untappd.com/b/gueuzerie-tilquin-oude-rhubarbe-tilquin-a-l-ancienne-2021-2022/4788026",
        "gemini_update": {
            "brewery_name_en": "Gueuzerie Tilquin",
            "brewery_name_jp": "ティルカン",
            "beer_name_en": "Oude Rhubarbe Tilquin à l'Ancienne",
            "beer_name_jp": "オード ルバーブ ティルカン ア ランシエンヌ",
            "beer_name_core": "Oude Rhubarbe Tilquin à l'Ancienne",
            "search_hint": "Oude Rhubarbe Tilquin a l'Ancienne Gueuzerie Tilquin",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/gueuzerie-tilquin-oude-rhubarbe-tilquin-a-l-ancienne-2021-2022/4788026"
        }
    }
]

# 3. ローリング巡回 & 新規特定・是正Untappd詳細取得対象
BEER_REFRESH_URLS = [
    # 既存データのローリング巡回監査
    "https://untappd.com/b/topa-topa-brewing-company-level-line/1167318",
    "https://untappd.com/b/allagash-brewing-company-north-sky/3925456",
    "https://untappd.com/b/revision-brewing-company-ridgeline-glow/6743708",
    "https://untappd.com/b/revision-brewing-company-single-track-theory/6743718",
    "https://untappd.com/b/living-haus-beer-company-charlie/6484613",
    # 是正対象
    "https://untappd.com/b/geuzestekerij-de-cam-trosbessen-2018/2629281",
    "https://untappd.com/b/brasserie-des-franches-montagnes-bfm-abbaye-de-saint-bon-chien-2018/2946234",
    # 新規特定対象
    "https://untappd.com/b/het-boerenerf-eylenbosch-oude-kriek-oogst-2020/4366733",
    "https://untappd.com/b/het-boerenerf-eylenbosch-kers-kaneel-oogst-2021/4802153",
    "https://untappd.com/b/wildflower-brewing-and-blending-good-as-gold/2830809",
    "https://untappd.com/b/gueuzerie-tilquin-oude-rhubarbe-tilquin-a-l-ancienne-2021-2022/4788026",
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

    # 1. 誤紐付け是正
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned beer items...")
    for item in FIX_MISASSIGNED_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"  Fixing {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url)))

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

    # 3. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[3] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} audit beers...")
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

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

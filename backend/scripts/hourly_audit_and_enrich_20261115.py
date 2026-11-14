import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ & Untappd特定済み商品の登録（未エンリッチ最優先4件 + 未紐付けから特定した4件）
NEW_ENRICH_ITEMS = [
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003448",
        "name": "【Pink Grapefruit Alternative IPA/CraftRock】",
        "untappd_url": "https://untappd.com/b/craftrock-brewing-pink-grapefruit-alternative-ipa/7663863",
        "gemini_update": {
            "brewery_name_en": "Craftrock Brewing",
            "brewery_name_jp": "クラフトロック",
            "beer_name_en": "PINK GRAPEFRUIT ALTERNATIVE IPA",
            "beer_name_jp": "ピンクグレープフルーツ オルタナティブ IPA",
            "beer_name_core": "Pink Grapefruit Alternative IPA",
            "search_hint": "Pink Grapefruit Alternative IPA Craftrock Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/craftrock-brewing-pink-grapefruit-alternative-ipa/7663863"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003447",
        "name": "【ハード茶イダー/OK,ADAM】",
        "untappd_url": "https://untappd.com/b/ok-adam/7176397",
        "gemini_update": {
            "brewery_name_en": "OK,ADAM",
            "brewery_name_jp": "オーケーアダム",
            "beer_name_en": "Hard Cha-ider",
            "beer_name_jp": "ハード茶イダー",
            "beer_name_core": "ハード茶イダー",
            "search_hint": "ハード茶イダー Hard Cha-ider OK,ADAM",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ok-adam/7176397"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003446",
        "name": "【HEBE/OK,ADAM】",
        "untappd_url": "https://untappd.com/b/ok-adam-hebe/5816675",
        "gemini_update": {
            "brewery_name_en": "OK,ADAM",
            "brewery_name_jp": "オーケーアダム",
            "beer_name_en": "HEBE",
            "beer_name_jp": "ヘーベー",
            "beer_name_core": "HEBE",
            "search_hint": "HEBE OK,ADAM",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ok-adam-hebe/5816675"
        }
    },
    {
        "url": "https://maruho.shop/products/made-glorious-summer-440ml-thornbridge",
        "name": "Made Glorious Summer (collab w/De La Senne) 440ml/Thornbridge",
        "untappd_url": "https://untappd.com/b/thornbridge-brewery-made-glorious-summer/6778348",
        "gemini_update": {
            "brewery_name_en": "Thornbridge Brewery",
            "brewery_name_jp": "ソーンブリッジ",
            "beer_name_en": "Made Glorious Summer",
            "beer_name_jp": "メイド グロリアス サマー",
            "beer_name_core": "Made Glorious Summer",
            "search_hint": "Made Glorious Summer Thornbridge Brewery De La Senne",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/thornbridge-brewery-made-glorious-summer/6778348"
        }
    },
    {
        "url": "https://beervolta.com/?pid=171935615",
        "name": "ジェスターキング ヴァーナルダイカトマス / Jester King Vernal Dichotomous",
        "untappd_url": "https://untappd.com/b/jester-king-brewery-vernal-dichotomous-2022/4951090",
        "gemini_update": {
            "brewery_name_en": "Jester King Brewery",
            "brewery_name_jp": "ジェスターキング",
            "beer_name_en": "Vernal Dichotomous (2022)",
            "beer_name_jp": "ヴァーナル ダイカトマス (2022)",
            "beer_name_core": "Vernal Dichotomous",
            "search_hint": "Vernal Dichotomous Jester King Brewery 2022",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/jester-king-brewery-vernal-dichotomous-2022/4951090"
        }
    },
    {
        "url": "https://beervolta.com/?pid=171935606",
        "name": "ジェスターキング x ジャイガンティック セラータ / Jester King x Gigantic Serrata",
        "untappd_url": "https://untappd.com/b/jester-king-brewery-serrata/2533550",
        "gemini_update": {
            "brewery_name_en": "Jester King Brewery",
            "brewery_name_jp": "ジェスターキング",
            "beer_name_en": "Serrata",
            "beer_name_jp": "セラータ",
            "beer_name_core": "Serrata",
            "search_hint": "Serrata Jester King Brewery Gigantic",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/jester-king-brewery-serrata/2533550"
        }
    },
    {
        "url": "https://beervolta.com/?pid=192860655",
        "name": "トートピア : ビーフォビア 2026 | Totopia: B-phobia (2026)",
        "untappd_url": "https://untappd.com/b/totopia-brewery-b-phobia-2026/6808995",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "B-phobia (2026)",
            "beer_name_jp": "ビーフォビア 2026",
            "beer_name_core": "B-phobia",
            "search_hint": "B-phobia Totopia Brewery 2026",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-b-phobia-2026/6808995"
        }
    },
    {
        "url": "https://beervolta.com/?pid=174855981",
        "name": "シルヴァ ヴェヴァーチェ / Silva Ve va Che",
        "untappd_url": "https://untappd.com/b/silva-brewing-ve-va-che/3901258",
        "gemini_update": {
            "brewery_name_en": "Silva Brewing",
            "brewery_name_jp": "シルヴァブリューイング",
            "beer_name_en": "Vēˈ vä ˌ Chē",
            "beer_name_jp": "ヴェヴァーチェ",
            "beer_name_core": "Ve va Che",
            "search_hint": "Ve va Che Silva Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/silva-brewing-ve-va-che/3901258"
        }
    }
]

# 2. Untappd未登録商品の監査確認更新
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://maruho.shop/products/木樽熟成-山伏-tea-for-two-2-blonde-500ml-志賀高原ビール",
        "name": "木樽熟成 山伏 Tea for Two 2 blonde 500ml/志賀高原ビール",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten",
            "brewery_name_jp": "玉村本店",
            "beer_name_en": "Yama-Bushi Tea for Two 2 blonde",
            "beer_name_jp": "木樽熟成 山伏 Tea for Two 2 blonde",
            "beer_name_core": "Yama-Bushi Tea for Two",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    }
]

# 3. ローリング巡回・Untappd詳細取得＆更新対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/baeren-bier-our-hour-yuzu-cidre-2025-our-hour-2025/6623616",
    "https://untappd.com/b/baeren-brauerei-classic/39317",
    "https://untappd.com/b/baeren-bier-schwarz/42490",
    "https://untappd.com/b/firestone-walker-brewing-company-cali-squeeze-raspberry-lime/5678025",
    "https://untappd.com/b/faction-brewing-faction-hefe/5865081"
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

    # 1. 新規特定商品のエンリッチ登録
    logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} newly identified beer items...")
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

    # 2. 未登録ビールの監査日時更新
    logger.info(f"\n[2] Marking {len(UNREGISTERED_BEER_ITEMS)} unregistered items as audited...")
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

    # 3. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[3] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
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

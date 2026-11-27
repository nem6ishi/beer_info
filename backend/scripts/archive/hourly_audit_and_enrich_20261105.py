import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ & 未紐付け特定商品 (25件)
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品: アローム (RaR 6件, Ruse 5件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8281",
        "untappd_url": "https://untappd.com/b/rar-brewing-encapsulation-of-color/7151932",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x The Test Brewery",
            "brewery_name_jp": "ロアーブルーイング x ザ・テスト・ブルワリー",
            "beer_name_en": "Encapsulation of Color",
            "beer_name_jp": "エンカプセレーション・オブ・カラー",
            "beer_name_core": "Encapsulation of Color",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-encapsulation-of-color/7151932"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8280",
        "untappd_url": "https://untappd.com/b/rar-brewing-believing-makes-it-better/6852408",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Cloudwater Brew Co.",
            "brewery_name_jp": "ロアーブルーイング x クラウドウォーター",
            "beer_name_en": "Believing Makes It Better",
            "beer_name_jp": "ビリーヴィン・メイクス・イット・ベター",
            "beer_name_core": "Believing Makes It Better",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-believing-makes-it-better/6852408"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8279",
        "untappd_url": "https://untappd.com/b/rar-brewing-sleep-all-day-party-all-night/6961316",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Messorem",
            "brewery_name_jp": "ロアーブルーイング x メッソレム",
            "beer_name_en": "Sleep All Day Party All Night",
            "beer_name_jp": "スリープ・オール・デイ・パーティ・オール・ナイト",
            "beer_name_core": "Sleep All Day Party All Night",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-sleep-all-day-party-all-night/6961316"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8278",
        "untappd_url": "https://untappd.com/b/rar-brewing-got-your-back/6961326",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Mikkeller",
            "brewery_name_jp": "ロアーブルーイング x ミッケラー",
            "beer_name_en": "Got Your Back",
            "beer_name_jp": "ゴット・ユア・バック",
            "beer_name_core": "Got Your Back",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-got-your-back/6961326"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8277",
        "untappd_url": "https://untappd.com/b/rar-brewing-following-dreams/6920352",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Omnipollo",
            "brewery_name_jp": "ロアーブルーイング x オムニポロ",
            "beer_name_en": "Following Dreams",
            "beer_name_jp": "フォローイング・ドリームズ",
            "beer_name_core": "Following Dreams",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-following-dreams/6920352"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8276",
        "untappd_url": "https://untappd.com/b/rar-brewing-savior-from-the-sea/6924349",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Uchu Brewing",
            "brewery_name_jp": "ロアーブルーイング x うちゅうブルーイング",
            "beer_name_en": "Savior From the Sea",
            "beer_name_jp": "セイヴァー・フロム・ザ・シー",
            "beer_name_core": "Savior From the Sea",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-savior-from-the-sea/6924349"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8275",
        "untappd_url": "https://untappd.com/b/ruse-brewing-lava-lamp-potluck/6137738",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Lava Lamp Potluck",
            "beer_name_jp": "ラヴァ・ランプ・ポットラック",
            "beer_name_core": "Lava Lamp Potluck",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-lava-lamp-potluck/6137738"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8274",
        "untappd_url": "https://untappd.com/b/ruse-brewing-nectar-extracto/5901369",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Nectar Extracto",
            "beer_name_jp": "ネクター・エクストラクト",
            "beer_name_core": "Nectar Extracto",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-nectar-extracto/5901369"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8273",
        "untappd_url": "https://untappd.com/b/ruse-brewing-eternal-almost/6744008",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Eternal Almost",
            "beer_name_jp": "エターナル・オールモスト",
            "beer_name_core": "Eternal Almost",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-eternal-almost/6744008"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8272",
        "untappd_url": "https://untappd.com/b/ruse-brewing-the-winds-farewell/6676592",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "The Winds Farewell",
            "beer_name_jp": "ザ・ウィンズ・フェアウェル",
            "beer_name_core": "The Winds Farewell",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-the-winds-farewell/6676592"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8271",
        "untappd_url": "https://untappd.com/b/ruse-brewing-hemisphere-of-shadows/6569608",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Hemisphere of Shadows",
            "beer_name_jp": "ヘミスフィア・オブ・シャドウズ",
            "beer_name_core": "Hemisphere of Shadows",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-hemisphere-of-shadows/6569608"
        }
    },

    # --- 未エンリッチ商品: ちょうせいや (うちゅう2件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002606",
        "untappd_url": "https://untappd.com/b/uchu-brewing-ghost-in-the-nebula/7648425",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "GHOST IN THE NEBULA",
            "beer_name_jp": "ゴースト イン ザ ネビュラ",
            "beer_name_core": "GHOST IN THE NEBULA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-ghost-in-the-nebula/7648425"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000863",
        "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "OROCHI",
            "beer_name_jp": "オロチ",
            "beer_name_core": "OROCHI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855"
        }
    },

    # --- 未エンリッチ商品: BEER VOLTA (トートピア2件) ---
    {
        "url": "https://beervolta.com/?pid=194302780",
        "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-nigo/7656944",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia NIGORI",
            "beer_name_jp": "4周年ヨンフォビア-ニゴ(濁)",
            "beer_name_core": "4phobia NIGORI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-nigo/7656944"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194302779",
        "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-sumi/7656946",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia SUMI",
            "beer_name_jp": "4周年ヨンフォビア-スミ(澄)",
            "beer_name_core": "4phobia SUMI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-sumi/7656946"
        }
    },

    # --- 未エンリッチ商品: マルホ酒店 (Ruse 4件) ---
    {
        "url": "https://maruho.shop/products/eternal-almost-473ml-ruse",
        "untappd_url": "https://untappd.com/b/ruse-brewing-eternal-almost/6744008",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Eternal Almost",
            "beer_name_jp": "エターナル オールモスト",
            "beer_name_core": "Eternal Almost",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-eternal-almost/6744008"
        }
    },
    {
        "url": "https://maruho.shop/products/hemisphere-of-shadows-473ml-ruse",
        "untappd_url": "https://untappd.com/b/ruse-brewing-hemisphere-of-shadows/6569608",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Hemisphere of Shadows",
            "beer_name_jp": "ヘミスフィア オブ シャドウズ",
            "beer_name_core": "Hemisphere of Shadows",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-hemisphere-of-shadows/6569608"
        }
    },
    {
        "url": "https://maruho.shop/products/nectar-extracto-473ml-ruse",
        "untappd_url": "https://untappd.com/b/ruse-brewing-nectar-extracto/5901369",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "Nectar Extracto",
            "beer_name_jp": "ネクター エクストラクト",
            "beer_name_core": "Nectar Extracto",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-nectar-extracto/5901369"
        }
    },
    {
        "url": "https://maruho.shop/products/the-winds-farewell-473ml-ruse",
        "untappd_url": "https://untappd.com/b/ruse-brewing-the-winds-farewell/6676592",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルーズブリューイング",
            "beer_name_en": "The Winds Farewell",
            "beer_name_jp": "ザ ウィンズ フェアウェル",
            "beer_name_core": "The Winds Farewell",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-the-winds-farewell/6676592"
        }
    },

    # --- Untappd未紐付け在庫ビールから特定 (5件) ---
    {
        "url": "https://www.antenna-america.com/products/b116-c16036",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-calling-in-sick/5588477",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "Calling In Sick",
            "beer_name_jp": "コーリング イン シック",
            "beer_name_core": "Calling In Sick",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-calling-in-sick/5588477"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b039-c16010a",
        "untappd_url": "https://untappd.com/b/49th-state-brewing-alaska-blueberry-ale/6998995",
        "gemini_update": {
            "brewery_name_en": "49th State Brewing Company",
            "brewery_name_jp": "フォーティーナインス ステート ブルーイング カンパニー",
            "beer_name_en": "Alaska Blueberry Ale",
            "beer_name_jp": "アラスカン ブルーベリー",
            "beer_name_core": "Alaska Blueberry Ale",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/49th-state-brewing-alaska-blueberry-ale/6998995"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000124",
        "untappd_url": "https://untappd.com/b/be-easy-brewing-the-citrus-games-fruitstories2/7657114",
        "gemini_update": {
            "brewery_name_en": "Be Easy Brewing x Black Tide Brewing x West Coast Brewing",
            "brewery_name_jp": "ビーイージー x ブラックタイド x ウエストコースト",
            "beer_name_en": "The Citrus Games - #fruitstories2",
            "beer_name_jp": "#fruitstories2",
            "beer_name_core": "The Citrus Games - #fruitstories2",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/be-easy-brewing-the-citrus-games-fruitstories2/7657114"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229813",
        "untappd_url": "https://untappd.com/b/be-easy-brewing-the-citrus-games-fruitstories2/7657114",
        "gemini_update": {
            "brewery_name_en": "Be Easy Brewing x Black Tide Brewing x West Coast Brewing",
            "brewery_name_jp": "ビーイージー x ブラックタイド x ウエストコースト",
            "beer_name_en": "The Citrus Games - #fruitstories2",
            "beer_name_jp": "ザ・シトラスゲームズ - #fruitstories2",
            "beer_name_core": "The Citrus Games - #fruitstories2",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/be-easy-brewing-the-citrus-games-fruitstories2/7657114"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b116-c16037",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-no-fly-zone/6310908",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "No Fly Zone",
            "beer_name_jp": "ノー フライゾーン",
            "beer_name_core": "No Fly Zone",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-no-fly-zone/6310908"
        }
    }
]

# Untappd未登録ビールのステータス更新 (Untappd調査済み・未登録マーク)
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://151l.shop/?pid=194319375",
        "notes": "YMARKET Lupulin Nectar Turn A (∀) - 新商品・Untappd未登録"
    }
]

# 2. ローリング巡回・Untappd データの最新化対象 (6件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/revision-brewing-company-shadow/6802045",
    "https://untappd.com/b/paint-palette-brewing-chromatic-blast/6426640",
    "https://untappd.com/b/paint-palette-brewing-goodtimes-district/6915809",
    "https://untappd.com/b/paint-palette-brewing-tropic-boardwalk/6827065",
    "https://untappd.com/b/uchu-brewing-grand-cross/5612827",
    "https://untappd.com/b/flora-fermentation-siren/6047535"
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

    # 1. 新規エンリッチ & 未紐付け特定 (25件)
    logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} target beers...")
    for item in NEW_ENRICH_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"  Enriching {url} -> {untappd_url}")

        # gemini_data upsert
        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sb.table("gemini_data").upsert(gem_update, on_conflict="url").execute())

        # scraped_beers update
        run_db_op(lambda: sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url).execute())

        # untappd_data scrape & upsert
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute())
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 2. Untappd未登録商品の処理
    if UNREGISTERED_BEER_ITEMS:
        logger.info(f"\n[2] Updating {len(UNREGISTERED_BEER_ITEMS)} unregistered beer items (marking surveyed)...")
        for item in UNREGISTERED_BEER_ITEMS:
            url = item["url"]
            run_db_op(lambda: sb.table("scraped_beers").update({
                "untappd_url": None,
                "untappd_enriched_at": now_iso
            }).eq("url", url).execute())
            logger.info(f"  ✅ Marked surveyed (not on Untappd): {url} ({item['notes']})")

    # 3. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[3] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute())
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

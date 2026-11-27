import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付け特定5件 + 誤紐付け修正1件 = 計26件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先 20件) ---
    {
        "url": "https://151l.shop/?pid=194302657",
        "untappd_url": "https://untappd.com/b/rar-brewing-savior-from-the-sea/6924349",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Uchu Brewing",
            "brewery_name_jp": "RaR×うちゅう",
            "beer_name_en": "Savior From the Sea",
            "beer_name_jp": "セイヴァーフロムザシー",
            "beer_name_core": "Savior From the Sea",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-savior-from-the-sea/6924349"
        }
    },
    {
        "url": "https://151l.shop/?pid=194302725",
        "untappd_url": "https://untappd.com/b/rar-brewing-following-dreams/6920352",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Omnipollo",
            "brewery_name_jp": "RaR×オムニポロ",
            "beer_name_en": "Following Dreams",
            "beer_name_jp": "フォローイングザドリームス",
            "beer_name_core": "Following Dreams",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-following-dreams/6920352"
        }
    },
    {
        "url": "https://151l.shop/?pid=194302777",
        "untappd_url": "https://untappd.com/b/rar-brewing-got-your-back/6961326",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Mikkeller",
            "brewery_name_jp": "RaR×ミッケラー",
            "beer_name_en": "Got Your Back",
            "beer_name_jp": "ゲットユアバック",
            "beer_name_core": "Got Your Back",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-got-your-back/6961326"
        }
    },
    {
        "url": "https://151l.shop/?pid=194302830",
        "untappd_url": "https://untappd.com/b/rar-brewing-sleep-all-day-party-all-night/6961316",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Messorem",
            "brewery_name_jp": "RaR×メッソーレム",
            "beer_name_en": "Sleep All Day Party All Night",
            "beer_name_jp": "スリープオールデイパーティオールナイト",
            "beer_name_core": "Sleep All Day Party All Night",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-sleep-all-day-party-all-night/6961316"
        }
    },
    {
        "url": "https://151l.shop/?pid=194302865",
        "untappd_url": "https://untappd.com/b/rar-brewing-believing-makes-it-better/6852408",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Cloudwater Brew Co.",
            "brewery_name_jp": "RaR×クラウドウォーター",
            "beer_name_en": "Believing Makes It Better",
            "beer_name_jp": "ビリービンメイクスイットベター",
            "beer_name_core": "Believing Makes It Better",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-believing-makes-it-better/6852408"
        }
    },
    {
        "url": "https://151l.shop/?pid=194302897",
        "untappd_url": "https://untappd.com/b/rar-brewing-encapsulation-of-color/7151932",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x The Test Brewery",
            "brewery_name_jp": "RaR×テスト",
            "beer_name_en": "Encapsulation of Color",
            "beer_name_jp": "エンカプシュレーションオブカラー",
            "beer_name_core": "Encapsulation of Color",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-encapsulation-of-color/7151932"
        }
    },
    {
        "url": "https://151l.shop/?pid=194303045",
        "untappd_url": "https://untappd.com/b/ruse-brewing-hemisphere-of-shadows/6569608",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルース",
            "beer_name_en": "Hemisphere of Shadows",
            "beer_name_jp": "ヘミソフィアオブシャドウズ",
            "beer_name_core": "Hemisphere of Shadows",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-hemisphere-of-shadows/6569608"
        }
    },
    {
        "url": "https://151l.shop/?pid=194303163",
        "untappd_url": "https://untappd.com/b/ruse-brewing-the-winds-farewell/6676592",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルース",
            "beer_name_en": "The Winds Farewell",
            "beer_name_jp": "ザウィンズフェアウェル",
            "beer_name_core": "The Winds Farewell",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-the-winds-farewell/6676592"
        }
    },
    {
        "url": "https://151l.shop/?pid=194303181",
        "untappd_url": "https://untappd.com/b/ruse-brewing-eternal-almost/6744008",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルース",
            "beer_name_en": "Eternal Almost",
            "beer_name_jp": "エターナルオールモスト",
            "beer_name_core": "Eternal Almost",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-eternal-almost/6744008"
        }
    },
    {
        "url": "https://151l.shop/?pid=194303216",
        "untappd_url": "https://untappd.com/b/ruse-brewing-nectar-extracto/5901369",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルース",
            "beer_name_en": "Nectar Extracto",
            "beer_name_jp": "ネクターエクストラクト",
            "beer_name_core": "Nectar Extracto",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-nectar-extracto/5901369"
        }
    },
    {
        "url": "https://151l.shop/?pid=194303284",
        "untappd_url": "https://untappd.com/b/ruse-brewing-lava-lamp-potluck/6137738",
        "gemini_update": {
            "brewery_name_en": "Ruse Brewing",
            "brewery_name_jp": "ルース",
            "beer_name_en": "Lava Lamp Potluck",
            "beer_name_jp": "ラヴァランプポットラック",
            "beer_name_core": "Lava Lamp Potluck",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ruse-brewing-lava-lamp-potluck/6137738"
        }
    },
    {
        "url": "https://151l.shop/?pid=194302016",
        "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-sumi/7656946",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia SUMI",
            "beer_name_jp": "4フォビア 澄",
            "beer_name_core": "4phobia SUMI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-sumi/7656946"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301990",
        "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-nigo/7656944",
        "gemini_update": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トートピアブルワリー",
            "beer_name_en": "4phobia NIGORI",
            "beer_name_jp": "4フォビア 濁",
            "beer_name_core": "4phobia NIGORI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/totopia-brewery-4phobia-nigo/7656944"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301551",
        "untappd_url": "https://untappd.com/b/arrogant-consortia-arrogant-bastard-ale/18099",
        "gemini_update": {
            "brewery_name_en": "Arrogant Consortia (Stone Brewing)",
            "brewery_name_jp": "アロガントコンソーティア（ストーン）",
            "beer_name_en": "Arrogant Bastard Ale",
            "beer_name_jp": "アロガントバスタードエール",
            "beer_name_core": "Arrogant Bastard Ale",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/arrogant-consortia-arrogant-bastard-ale/18099"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301425",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-local-katana/5669176",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "Local Katana",
            "beer_name_jp": "ローカルカタナ",
            "beer_name_core": "Local Katana",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-local-katana/5669176"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301433",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-god-of-pour/4219243",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "God of Pour",
            "beer_name_jp": "ゴッドオブプアー",
            "beer_name_core": "God of Pour",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-god-of-pour/4219243"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301461",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-calling-in-sick/5588477",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "Calling In Sick",
            "beer_name_jp": "コーリングインシック",
            "beer_name_core": "Calling In Sick",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-calling-in-sick/5588477"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301481",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-true-brewmance/1343324",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "True Brewmance",
            "beer_name_jp": "トゥルーブリューマンス",
            "beer_name_core": "True Brewmance",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-true-brewmance/1343324"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301497",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-no-fly-zone/6310908",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "No Fly Zone",
            "beer_name_jp": "ノーフライゾーン",
            "beer_name_core": "No Fly Zone",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-no-fly-zone/6310908"
        }
    },
    {
        "url": "https://151l.shop/?pid=194301543",
        "untappd_url": "https://untappd.com/b/8-bit-brewing-company-pillars-of-kings/4768791",
        "gemini_update": {
            "brewery_name_en": "8 bit Brewing Company",
            "brewery_name_jp": "エイトビット",
            "beer_name_en": "Pillars of Kings",
            "beer_name_jp": "ピラーズオブキングス",
            "beer_name_core": "Pillars of Kings",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/8-bit-brewing-company-pillars-of-kings/4768791"
        }
    },

    # --- Untappd未紐付け在庫ビールから特定 (5件) ---
    {
        "url": "https://www.antenna-america.com/products/b106-c16005",
        "untappd_url": "https://untappd.com/b/east-brother-beer-company-gold-ipa/1822195",
        "gemini_update": {
            "brewery_name_en": "East Brother Beer Company",
            "brewery_name_jp": "イーストブラザービール",
            "beer_name_en": "Gold IPA",
            "beer_name_jp": "ゴールドIPA",
            "beer_name_core": "Gold IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/east-brother-beer-company-gold-ipa/1822195"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b124-c12006a",
        "untappd_url": "https://untappd.com/b/bootstrap-brewing-double-lush-puppy-juicy-ipa/5727060",
        "gemini_update": {
            "brewery_name_en": "Bootstrap Brewing Company",
            "brewery_name_jp": "ブートストラップブルーイング",
            "beer_name_en": "Double Lush Puppy Juicy Double IPA",
            "beer_name_jp": "ダブル ラッシュ パピー",
            "beer_name_core": "Double Lush Puppy",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/bootstrap-brewing-double-lush-puppy-juicy-ipa/5727060"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8257",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-dawn-in-ube/6202152",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Company",
            "brewery_name_jp": "エンボールデン",
            "beer_name_en": "Shogun - Dawn in Ube",
            "beer_name_jp": "ショーグン - ドーン・イン・ウベ",
            "beer_name_core": "Dawn in Ube",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-dawn-in-ube/6202152"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8256",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-rice-lager/6829108",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Company",
            "brewery_name_jp": "エンボールデン",
            "beer_name_en": "Shogun - Japanese Rice Lager",
            "beer_name_jp": "ショーグン - ジャパニーズ・ライスラガー",
            "beer_name_core": "Rice Lager",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-rice-lager/6829108"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8251",
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

    # --- 誤紐付け是正・修正 (1件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000272",
        "untappd_url": "https://untappd.com/b/minoh-beer-minoh-w-ipa/47229",
        "gemini_update": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "W-IPA",
            "beer_name_jp": "W-IPA",
            "beer_name_core": "W-IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minoh-beer-minoh-w-ipa/47229"
        }
    }
]

# 2. ローリング巡回・Untappd データの最新化対象（4件）
BEER_REFRESH_URLS = [
    "https://untappd.com/b/minoh-beer-tea-bitter/6754566",
    "https://untappd.com/b/minoh-beer-high-collar-pils/6779247",
    "https://untappd.com/b/minoh-beer-minoh-osaru-ipa-ipa/329658",
    "https://untappd.com/b/namachan-brewing-yamitsuki-ale-mapo-10th-batch/6808022"
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

    # 1. 新規エンリッチ & 修正 (26件)
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

    # 2. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[2] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
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

    # 3. マテリアライズドビューのリフレッシュ
    logger.info("\n[3] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

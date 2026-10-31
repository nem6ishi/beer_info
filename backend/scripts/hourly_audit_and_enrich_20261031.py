import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付け特定1件 + 誤紐付け是正1件 = 計22件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先 20件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002553",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-nelson-south/7643828",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Garston - Nelson South",
            "beer_name_jp": "Garston - Nelson South",
            "beer_name_core": "Garston - Nelson South",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-nelson-south/7643828"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001519",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-endgame-magic/4794213",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Endgame Magic",
            "beer_name_jp": "Endgame Magic",
            "beer_name_core": "Endgame Magic",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-endgame-magic/4794213"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000094",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-starwatcher/3314985",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Starwatcher",
            "beer_name_jp": "Starwatcher",
            "beer_name_core": "Starwatcher",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-starwatcher/3314985"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003150",
        "untappd_url": "https://untappd.com/b/mangosteen-brewing-lab-yaki-imo-ale/6648564",
        "gemini_update": {
            "brewery_name_en": "MANGOSTEEN BREWING LAB / 万珍醸造",
            "brewery_name_jp": "万珍醸造",
            "beer_name_en": "YAKI-IMO ALE",
            "beer_name_jp": "YAKI-IMO ALE",
            "beer_name_core": "YAKI-IMO ALE",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mangosteen-brewing-lab-yaki-imo-ale/6648564"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003438",
        "untappd_url": "https://untappd.com/b/namachan-brewing-himarayan-pepper-ale/6494668",
        "gemini_update": {
            "brewery_name_en": "Namachan Brewing",
            "brewery_name_jp": "NAMACHAんブルーイング",
            "beer_name_en": "ヒマラヤンペッパーエール",
            "beer_name_jp": "ヒマラヤンペッパーエール",
            "beer_name_core": "ヒマラヤンペッパーエール",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/namachan-brewing-himarayan-pepper-ale/6494668"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003437",
        "untappd_url": "https://untappd.com/b/namachan-brewing/6981561",
        "gemini_update": {
            "brewery_name_en": "Namachan Brewing",
            "brewery_name_jp": "NAMACHAんブルーイング",
            "beer_name_en": "ふにゃなま",
            "beer_name_jp": "ふにゃなま",
            "beer_name_core": "ふにゃなま",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/namachan-brewing/6981561"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002978",
        "untappd_url": "https://untappd.com/b/uchu-brewing-sugoi-ipa/6746104",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "SUGOI IPA",
            "beer_name_jp": "すごいIPA",
            "beer_name_core": "SUGOI IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-sugoi-ipa/6746104"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002630",
        "untappd_url": "https://untappd.com/b/isekado-hop-nyaon-13th-fleet-13/6972729",
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "HOP NYAON 13th Fleet",
            "beer_name_jp": "ホップにゃおん第13艦隊",
            "beer_name_core": "ホップにゃおん第13艦隊",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/isekado-hop-nyaon-13th-fleet-13/6972729"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001986",
        "untappd_url": "https://untappd.com/b/isekado/7176491",
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Smoked Dashi",
            "beer_name_jp": "燻しだし",
            "beer_name_core": "燻しだし",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/isekado/7176491"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002533",
        "untappd_url": "https://untappd.com/b/ise-kadoya-brain-melting-ultra-heaven-3-x-ipa/6653697",
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Brain-melting Ultra Heaven 3 X IPA",
            "beer_name_jp": "脳がとろけるウルトラヘヴン",
            "beer_name_core": "脳がとろけるウルトラヘヴン",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ise-kadoya-brain-melting-ultra-heaven-3-x-ipa/6653697"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000495",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-ipa-2025/6377131",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Shiga Kogen Fresh Hop IPA",
            "beer_name_jp": "Fresh Hop IPA",
            "beer_name_core": "Fresh Hop",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-ipa-2025/6377131"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003431",
        "untappd_url": "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-festweisse-tap04/11827",
        "gemini_update": {
            "brewery_name_en": "Schneider Weisse G. Schneider & Sohn",
            "brewery_name_jp": "シュナイダー・ヴァイセ",
            "beer_name_en": "Festweisse (TAP04)",
            "beer_name_jp": "TAP4 Festweisse",
            "beer_name_core": "Festweisse TAP4",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-festweisse-tap04/11827"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003430",
        "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-a-la-grodziskie/6349826",
        "gemini_update": {
            "brewery_name_en": "Schlenkerla (\"Heller-Bräu\" Trum)",
            "brewery_name_jp": "シュレンケラ（ヘラーブロイ）",
            "beer_name_en": "Aecht Schlenkerla á la Grodziskie",
            "beer_name_jp": "Schlenkerla a la Grodziskie",
            "beer_name_core": "Schlenkerla a la Grodziskie",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-a-la-grodziskie/6349826"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003392",
        "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-erle-schwarzbier/5456891",
        "gemini_update": {
            "brewery_name_en": "Schlenkerla (\"Heller-Bräu\" Trum)",
            "brewery_name_jp": "シュレンケラ（ヘラーブロイ）",
            "beer_name_en": "Aecht Schlenkerla Erle – Schwarzbier",
            "beer_name_jp": "Schlenkerla Erle",
            "beer_name_core": "Schlenkerla Erle",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-erle-schwarzbier/5456891"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000731",
        "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-weizen/472",
        "gemini_update": {
            "brewery_name_en": "Schlenkerla (\"Heller-Bräu\" Trum)",
            "brewery_name_jp": "シュレンケラ（ヘラーブロイ）",
            "beer_name_en": "Aecht Schlenkerla Rauchbier – Weizen",
            "beer_name_jp": "Schlenkerla Weizen",
            "beer_name_core": "Schlenkerla Weizen",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-weizen/472"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000464",
        "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-marzen/471",
        "gemini_update": {
            "brewery_name_en": "Schlenkerla (\"Heller-Bräu\" Trum)",
            "brewery_name_jp": "シュレンケラ（ヘラーブロイ）",
            "beer_name_en": "Aecht Schlenkerla Rauchbier – Märzen",
            "beer_name_jp": "Schlenkerla Märzen",
            "beer_name_core": "Märzen",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-marzen/471"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000726",
        "untappd_url": "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-aventinus-eisbock-tap09/67996",
        "gemini_update": {
            "brewery_name_en": "Schneider Weisse G. Schneider & Sohn",
            "brewery_name_jp": "シュナイダー・ヴァイセ",
            "beer_name_en": "Aventinus Eisbock (TAP09)",
            "beer_name_jp": "アヴェンティヌス アイスボック",
            "beer_name_core": "Aventinus Eisbock",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-aventinus-eisbock-tap09/67996"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003396",
        "untappd_url": "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-original-tap07/11982",
        "gemini_update": {
            "brewery_name_en": "Schneider Weisse G. Schneider & Sohn",
            "brewery_name_jp": "シュナイダー・ヴァイセ",
            "beer_name_en": "Original (TAP07)",
            "beer_name_jp": "TAP7 Original",
            "beer_name_core": "Original TAP07",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-original-tap07/11982"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194241477",
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
        "url": "https://beervolta.com/?pid=194229885",
        "untappd_url": "https://untappd.com/b/rikri-brewing-flypaper/7019033",
        "gemini_update": {
            "brewery_name_en": "RIKRI BREWING",
            "brewery_name_jp": "リクリブルーイング",
            "beer_name_en": "Flypaper",
            "beer_name_jp": "フライペーパー",
            "beer_name_core": "Flypaper",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rikri-brewing-flypaper/7019033"
        }
    },
    # --- Untappd未紐付けから特定したアイテム (1件) ---
    {
        "url": "https://151l.shop/?pid=194188474",
        "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-school-of-croc/5495176",
        "gemini_update": {
            "brewery_name_en": "Kings County Brewers Collective",
            "brewery_name_jp": "キングスカウンティ ブルワーズ コレクティブ",
            "beer_name_en": "School of Croc",
            "beer_name_jp": "スクールオブクロック",
            "beer_name_core": "School of Croc",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-school-of-croc/5495176"
        }
    },
    # --- 誤紐付け是正アイテム (1件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7936",
        "untappd_url": "https://untappd.com/b/isekado-sakekasu-hazy-ipa-zaku/6783202",
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Sakekasu Hazy IPA ZAKU 夏酒",
            "beer_name_jp": "Sakekasu Hazy IPA ZAKU 夏酒",
            "beer_name_core": "Sakekasu Hazy IPA ZAKU 夏酒",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/isekado-sakekasu-hazy-ipa-zaku/6783202"
        }
    }
]

# 2. 未登録確認済み・調査タイムスタンプ更新対象 (Untappd未登録ビール 4件)
UNREGISTERED_INSPECTED_URLS = [
    "https://maruho.shop/products/アオイト-750ml-甘く浮く",                         # 甘く浮く / アオイト
    "https://151l.shop/?pid=192919839",                                         # ISEKADO / KADOLABO 039
    "https://151l.shop/?pid=193631430",                                         # FARMENTRY / お茶！大和
    "https://www.arome.jp/products/detail.php?product_id=8208",                  # VERTERE / Cotinus #1
]

# 3. ローリング巡回・Untappd データの最新化対象 (4件のユニークURL)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/unsung-brewing-co-the-outcast/6491038",
    "https://untappd.com/b/faction-brewing-hella-strata/3658132",
    "https://untappd.com/b/almanac-adventureland-peach-pop/6700281",
    "https://untappd.com/b/teenage-brewing-sugar-pack/6836569"
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

    # 1. 新規エンリッチ & 修正
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

    # 2. 未登録確認済みアイテムの調査タイムスタンプ更新
    logger.info(f"\n[2] Updating inspected timestamp for {len(UNREGISTERED_INSPECTED_URLS)} untappd-unregistered beers...")
    for url in UNREGISTERED_INSPECTED_URLS:
        run_db_op(lambda: sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", url).execute())
        logger.info(f"  ✅ Timestamp updated for: {url}")

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

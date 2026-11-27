import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付け特定5件 = 計25件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先 20件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002205",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-fruitstories-2-the-citrus-games/7643827",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "#fruitstories 2 - The Citrus Games -",
            "beer_name_jp": "#fruitstories 2",
            "beer_name_core": "The Citrus Games",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-fruitstories-2-the-citrus-games/7643827"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002208",
        "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675",
        "gemini_update": {
            "brewery_name_en": "Black Tide Brewing",
            "brewery_name_jp": "ブラックタイドブルーイング",
            "beer_name_en": "#FRUITSTORIES 2 = the Citrus Games =",
            "beer_name_jp": "#fruitstories 2",
            "beer_name_core": "fruitstories 2",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229883",
        "untappd_url": "https://untappd.com/b/rikri-brewing-big-hoppa/6609159",
        "gemini_update": {
            "brewery_name_en": "RIKRI BREWING",
            "brewery_name_jp": "リクリブルーイング",
            "beer_name_en": "Big Hoppa",
            "beer_name_jp": "Big Hoppa",
            "beer_name_core": "Big Hoppa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rikri-brewing-big-hoppa/6609159"
        }
    },
    {
        "url": "https://151l.shop/?pid=194236852",
        "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing × Brujos Brewing",
            "brewery_name_jp": "うちゅうブルーイング × ブルホスブルーイング",
            "beer_name_en": "Orochi",
            "beer_name_jp": "おろち",
            "beer_name_core": "Orochi",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855"
        }
    },
    {
        "url": "https://151l.shop/?pid=194236894",
        "untappd_url": "https://untappd.com/b/uchu-brewing-ghost-in-the-nebula/7648425",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing x Messorem",
            "brewery_name_jp": "うちゅうブルーイング×メッソーレム",
            "beer_name_en": "GHOST IN THE NEBULA",
            "beer_name_jp": "ゴーストインザネビュラ",
            "beer_name_core": "GHOST IN THE NEBULA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-ghost-in-the-nebula/7648425"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229837",
        "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855",
        "gemini_update": {
            "brewery_name_en": "UCHU x Brujos",
            "brewery_name_jp": "うちゅう x ブルホス",
            "beer_name_en": "OROCHI",
            "beer_name_jp": "おろち",
            "beer_name_core": "OROCHI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229836",
        "untappd_url": "https://untappd.com/b/uchu-brewing-vibe-uchu-vibe-abv-0-5ver/7648445",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙VIBE ABV 0.5ver",
            "beer_name_jp": "宇宙VIBE ABV 0.5ver",
            "beer_name_core": "宇宙VIBE",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-vibe-uchu-vibe-abv-0-5ver/7648445"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229817",
        "untappd_url": "https://untappd.com/b/black-tide-brewing-mallow-attack/7640057",
        "gemini_update": {
            "brewery_name_en": "Black Tide Brewing",
            "brewery_name_jp": "ブラックタイドブルーイング",
            "beer_name_en": "#522 Mallow Attack",
            "beer_name_jp": "#522 Mallow Attack",
            "beer_name_core": "Mallow Attack",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/black-tide-brewing-mallow-attack/7640057"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229816",
        "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675",
        "gemini_update": {
            "brewery_name_en": "Black Tide Brewing",
            "brewery_name_jp": "ブラックタイドブルーイング",
            "beer_name_en": "#521 #fruitstories2",
            "beer_name_jp": "#521 #fruitstories2",
            "beer_name_core": "fruitstories 2",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229815",
        "untappd_url": "https://untappd.com/b/be-easy-brewing-be-easy-dosa-yukkosa/7640062",
        "gemini_update": {
            "brewery_name_en": "Be Easy Brewing",
            "brewery_name_jp": "ビーイージーブルーイング",
            "beer_name_en": "Dosa?Yukkosa! - West Coast IPA",
            "beer_name_jp": "どさ！ゆっこさ！",
            "beer_name_core": "Dosa?Yukkosa!",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/be-easy-brewing-be-easy-dosa-yukkosa/7640062"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229814",
        "untappd_url": "https://untappd.com/b/be-easy-brewing-lilikoi/7616706",
        "gemini_update": {
            "brewery_name_en": "Be Easy Brewing",
            "brewery_name_jp": "ビーイージーブルーイング",
            "beer_name_en": "Lilikoi",
            "beer_name_jp": "リリコイ",
            "beer_name_core": "Lilikoi",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/be-easy-brewing-lilikoi/7616706"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229812",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-motueka-south/7643829",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Garston - Motueka South",
            "beer_name_jp": "ガーストン モトゥエカ サウス",
            "beer_name_core": "Garston - Motueka South",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-motueka-south/7643829"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229811",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-nelson-south/7643828",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Garston - Nelson South",
            "beer_name_jp": "ガーストン ネルソン サウス",
            "beer_name_core": "Garston - Nelson South",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-nelson-south/7643828"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194229810",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-fruitstories-2-the-citrus-games/7643827",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "#fruitstories 2 - The Citrus Games -",
            "beer_name_jp": "ザ・シトラスゲームズ",
            "beer_name_core": "The Citrus Games",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-fruitstories-2-the-citrus-games/7643827"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194188458",
        "untappd_url": "https://untappd.com/b/uchu-brewing-relax-uchu-relax-2025/5974657",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙Relax (UCHU Relax)",
            "beer_name_jp": "宇宙Relax",
            "beer_name_core": "UCHU Relax",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-relax-uchu-relax-2025/5974657"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8253",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-nelson-south/7643828",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Garston - Nelson South",
            "beer_name_jp": "ガーストン・ネルソン・サウス",
            "beer_name_core": "Garston - Nelson South",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-nelson-south/7643828"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8223",
        "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675",
        "gemini_update": {
            "brewery_name_en": "Black Tide Brewing",
            "brewery_name_jp": "ブラックタイドブルーイング",
            "beer_name_en": "#FRUITSTORIES 2 = the Citrus Games =",
            "beer_name_jp": "フルーツストーリーズ2",
            "beer_name_core": "fruitstories 2",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675"
        }
    },
    {
        "url": "https://maruho.shop/products/to-the-stars-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-to-the-stars/6964939",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "To The Stars",
            "beer_name_jp": "トゥ ザ スターズ",
            "beer_name_core": "To The Stars",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-to-the-stars/6964939"
        }
    },
    {
        "url": "https://maruho.shop/products/dead-quiet-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-finback-dead-quiet/7611491",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Dead Quiet",
            "beer_name_jp": "デッド クワイエット",
            "beer_name_core": "Dead Quiet",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-finback-dead-quiet/7611491"
        }
    },
    {
        "url": "https://maruho.shop/products/looks-good-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-looks-good/6964936",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Looks Good",
            "beer_name_jp": "ルックス グッド",
            "beer_name_core": "Looks Good",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-looks-good/6964936"
        }
    },
    # --- 未紐付け在庫ビール特定アイテム (5件) ---
    {
        "url": "https://maruho.shop/products/paper-maker-473ml-grains-of-wrath",
        "untappd_url": "https://untappd.com/b/grains-of-wrath-papermaker-pale/2527807",
        "gemini_update": {
            "brewery_name_en": "Grains Of Wrath",
            "brewery_name_jp": "グレインズ オブ ラス",
            "beer_name_en": "Papermaker Pale",
            "beer_name_jp": "ペーパーメーカー",
            "beer_name_core": "Papermaker",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grains-of-wrath-papermaker-pale/2527807"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8250",
        "untappd_url": "https://untappd.com/b/nobody-brewing-rooftop-concert/7648628",
        "gemini_update": {
            "brewery_name_en": "Nobody Brewing",
            "brewery_name_jp": "ノーバディー・ブルーイング",
            "beer_name_en": "Rooftop Concert",
            "beer_name_jp": "ルーフトップ・コンサート",
            "beer_name_core": "Rooftop Concert",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/nobody-brewing-rooftop-concert/7648628"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8246",
        "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-biere-des-charentes/5400675",
        "gemini_update": {
            "brewery_name_en": "Blind Enthusiasm Brewing",
            "brewery_name_jp": "ブラインドエンスージアズム",
            "beer_name_en": "Bière des Charentes",
            "beer_name_jp": "ビエール・デ・シャラント",
            "beer_name_core": "Bière des Charentes",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-biere-des-charentes/5400675"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8243",
        "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-spontaneous-manifesto-2023/5979509",
        "gemini_update": {
            "brewery_name_en": "Blind Enthusiasm Brewing",
            "brewery_name_jp": "ブラインドエンスージアズム",
            "beer_name_en": "Spontaneous Manifesto 2023",
            "beer_name_jp": "スポンテニアス・マニフェスト 2023",
            "beer_name_core": "Spontaneous Manifesto",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-spontaneous-manifesto-2023/5979509"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8244",
        "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-fruitful-pursuits-cherry-2024/6775118",
        "gemini_update": {
            "brewery_name_en": "Blind Enthusiasm Brewing",
            "brewery_name_jp": "ブラインドエンスージアズム",
            "beer_name_en": "Fruitful Pursuits: Cherry 2024",
            "beer_name_jp": "フルーツフル・パースーツ・チェリー 2024",
            "beer_name_core": "Fruitful Pursuits: Cherry",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-fruitful-pursuits-cherry-2024/6775118"
        }
    }
]

# 2. 未登録確認済みアイテム（今回はなし）
UNREGISTERED_INSPECTED_URLS = []

# 3. ローリング巡回・Untappd データの最新化対象（3件のユニークURL）
BEER_REFRESH_URLS = [
    "https://untappd.com/b/moonraker-brewing-company-the-holy-hermit/1877806",
    "https://untappd.com/b/kyoto-brewing-company-birds-of-fire/6905598",
    "https://untappd.com/b/nobody-brewing-the-house/6681715"
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

    # 1. 新規エンリッチ & 修正 (25件)
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

    # 2. 未登録確認済みアイテムの調査タイムスタンプ更新（今回は0件）
    if UNREGISTERED_INSPECTED_URLS:
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

import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def safe_execute(query, max_retries=3):
    for attempt in range(max_retries):
        try:
            return query.execute()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            logger.warning(f"Database query retry {attempt + 1}/{max_retries} due to {e}")
            time.sleep(2)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付けから特定1件 = 計21件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8260",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-packerland-pilsner/501979",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド",
            "beer_name_en": "Packerland Pilsner",
            "beer_name_jp": "パッカーランド・ピルスナー",
            "beer_name_core": "Packerland Pilsner",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-packerland-pilsner/501979"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8259",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-football-is-better-with-cheese-and-sausage/6552719",
        "gemini_update": {
            "brewery_name_en": "Hinterland x Hop Butcher",
            "brewery_name_jp": "ヒンターランド x ホップブッチャー",
            "beer_name_en": "Football Is Better With Sausage and Cheese",
            "beer_name_jp": "フットボール・イズ・ベター・ウィズ・ソーセージ・アンド・チーズ",
            "beer_name_core": "Football Is Better With Sausage and Cheese",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-football-is-better-with-cheese-and-sausage/6552719"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=5996",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-blueberry-wheat/4542419",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド",
            "beer_name_en": "Blueberry Wheat",
            "beer_name_jp": "ブルーベリーウィート",
            "beer_name_core": "Blueberry Wheat",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-blueberry-wheat/4542419"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8264",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-hat-dance/3640739",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘヴィーリフ",
            "beer_name_en": "Hat Dance",
            "beer_name_jp": "ハットダンス",
            "beer_name_core": "Hat Dance",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-hat-dance/3640739"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8263",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-daisy-glaze/2459386",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘヴィーリフ",
            "beer_name_en": "Daisy Glaze",
            "beer_name_jp": "デイジーグレイズ",
            "beer_name_core": "Daisy Glaze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-daisy-glaze/2459386"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8262",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-n-i-b/5487271",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘヴィーリフ",
            "beer_name_en": "N.I.B.",
            "beer_name_jp": "N.I.B.",
            "beer_name_core": "N.I.B.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-n-i-b/5487271"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8261",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-raglan-irish-red/608392",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘヴィーリフ",
            "beer_name_en": "Raglan",
            "beer_name_jp": "ラグラン",
            "beer_name_core": "Raglan",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-raglan-irish-red/608392"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=4527",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-velvet-underbrown/358026",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘヴィーリフ",
            "beer_name_en": "Velvet Underbrown",
            "beer_name_jp": "ヴェルヴェット・アンダーブラウン",
            "beer_name_core": "Velvet Underbrown",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-velvet-underbrown/358026"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=4524",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-disco-apocalypse/3522337",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘヴィーリフ",
            "beer_name_en": "Disco Apocalypse",
            "beer_name_jp": "ディスコ・アポカリプス",
            "beer_name_core": "Disco Apocalypse",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-disco-apocalypse/3522337"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8258",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-dusk-in-kyoto/6026740",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Co.",
            "brewery_name_jp": "エンボールデン",
            "beer_name_en": "Shogun - Dusk in Kyoto",
            "beer_name_jp": "ショーグン - ダスク・イン・キョウト",
            "beer_name_core": "Shogun - Dusk in Kyoto",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-dusk-in-kyoto/6026740"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=4311",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-midnight-in-tokyo/5933123",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Company",
            "brewery_name_jp": "エンボールデン",
            "beer_name_en": "Shogun - Midnight in Tokyo",
            "beer_name_jp": "ショーグン - ミッドナイト・イン・トーキョー",
            "beer_name_core": "Shogun - Midnight in Tokyo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-midnight-in-tokyo/5933123"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=2693",
        "untappd_url": "https://untappd.com/b/inkhorn-brewing-baby-ruptor-2026/7646903",
        "gemini_update": {
            "brewery_name_en": "Inkhorn Brewing",
            "brewery_name_jp": "インクホーン",
            "beer_name_en": "Baby Raptor 2026",
            "beer_name_jp": "ベイビーラプター 2026",
            "beer_name_core": "Baby Raptor 2026",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/inkhorn-brewing-baby-ruptor-2026/7646903"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8255",
        "untappd_url": "https://untappd.com/b/vertere-vanitas/7648720",
        "gemini_update": {
            "brewery_name_en": "VERTERE x Kyoto Brewing Co.",
            "brewery_name_jp": "バテレ x 京都醸造",
            "beer_name_en": "Vanitas",
            "beer_name_jp": "ヴァニタス",
            "beer_name_core": "Vanitas",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-vanitas/7648720"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8254",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-motueka-south/7643829",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Garston - Motueka South",
            "beer_name_jp": "ガーストン・モチュエカ・サウス",
            "beer_name_core": "Garston - Motueka South",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-garston-motueka-south/7643829"
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8252",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-fruitstories-2-the-citrus-games/7643827",
        "gemini_update": {
            "brewery_name_en": "West Coast x Be Easy x Black Tide",
            "brewery_name_jp": "ウエストコースト x ビーイージー x ブラックタイド",
            "beer_name_en": "fruitstories 2 - The Citrus Games -",
            "beer_name_jp": "フルーツストーリーズ 2 - ザ・シトラスゲームズ -",
            "beer_name_core": "fruitstories 2 - The Citrus Games -",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-fruitstories-2-the-citrus-games/7643827"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8223",
        "untappd_url": "https://untappd.com/b/black-tide-brewing-fruitstories-2-the-citrus-games/7650675",
        "gemini_update": {
            "brewery_name_en": "Black Tide x Be Easy x West Coast",
            "brewery_name_jp": "ブラックタイド x ビーイージー x ウエストコースト",
            "beer_name_en": "#fruitstories 2",
            "beer_name_jp": "フルーツストーリーズ2",
            "beer_name_core": "#fruitstories 2",
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
    # --- 未紐付け在庫から特定したアイテム ---
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
    }
]

# 2. 未登録確認済み・調査タイムスタンプ更新対象 (Untappd未登録のビール)
UNREGISTERED_INSPECTED_URLS = [
    "https://maruho.shop/products/アオイト-750ml-甘く浮く",              # 甘く浮く / アオイト
    "https://151l.shop/?pid=192919839",                                 # ISEKADOYA / KADOLABO 039
    "https://www.arome.jp/products/detail.php?product_id=8208",          # VERTERE / Cotinus #1
    "https://151l.shop/?pid=193631430",                                 # FARMENTRY / OCHA! YAMATO
]

# 3. ローリング巡回・Untappd データの最新化対象 (5件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/vertere-achillea/6709616",
    "https://untappd.com/b/embolden-beer-company-litehouse/4968769",
    "https://untappd.com/b/embolden-beer-company-broken-record/4947284",
    "https://untappd.com/b/mangosteen-brewing-lab-yaki-imo-ale/6648564",
    "https://untappd.com/b/uchu-brewing-relax-uchu-relax-2025/5974657",
]

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
        safe_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url"))

        # scraped_beers update
        safe_execute(sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url))

        # untappd_data scrape & upsert
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            safe_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url"))
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 2. 未登録確認済みアイテムの調査タイムスタンプ更新
    logger.info(f"\n[2] Updating inspected timestamp for {len(UNREGISTERED_INSPECTED_URLS)} untappd-unregistered beers...")
    for url in UNREGISTERED_INSPECTED_URLS:
        safe_execute(sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", url))
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
            safe_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url"))
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

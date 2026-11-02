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
        "url": "https://www.arome.jp/products/detail.php?product_id=8268",
        "untappd_url": "https://untappd.com/b/uchu-brewing-vibe-uchu-vibe-abv-0-5ver/7648445",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "UCHU VIBE ABV 0.5ver",
            "beer_name_jp": "宇宙VIBE ABV 0.5ver",
            "beer_name_core": "UCHU VIBE",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-vibe-uchu-vibe-abv-0-5ver/7648445"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8267",
        "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855",
        "gemini_update": {
            "brewery_name_en": "UCHU Brewing × Brujos Brewing",
            "brewery_name_jp": "うちゅうブルーイング × ブルホスブルーイング",
            "beer_name_en": "Orochi",
            "beer_name_jp": "オロチ",
            "beer_name_core": "Orochi",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-orochi/7646855"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8265",
        "untappd_url": "https://untappd.com/b/brouwerij-der-trappisten-van-westmalle-westmalle-trappist-extra/31175",
        "gemini_update": {
            "brewery_name_en": "Brouwerij der Trappisten van Westmalle",
            "brewery_name_jp": "ウェストマール",
            "beer_name_en": "Westmalle Trappist Extra",
            "beer_name_jp": "エクストラ",
            "beer_name_core": "Extra",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brouwerij-der-trappisten-van-westmalle-westmalle-trappist-extra/31175"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=672",
        "untappd_url": "https://untappd.com/b/abbaye-notre-dame-de-saint-remy-trappistes-rochefort-8/11473",
        "gemini_update": {
            "brewery_name_en": "Abbaye Notre-Dame de Saint-Rémy",
            "brewery_name_jp": "ロシュフォール",
            "beer_name_en": "Trappistes Rochefort 8",
            "beer_name_jp": "ロシュフォール 8",
            "beer_name_core": "Rochefort 8",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/abbaye-notre-dame-de-saint-remy-trappistes-rochefort-8/11473"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8266",
        "untappd_url": "https://untappd.com/b/de-achelse-kluis-achel-tripel/1428",
        "gemini_update": {
            "brewery_name_en": "De Achelse Kluis",
            "brewery_name_jp": "アヘル",
            "beer_name_en": "Achel Tripel",
            "beer_name_jp": "アヘル・トリペル",
            "beer_name_core": "Achel Tripel",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/de-achelse-kluis-achel-tripel/1428"
        }
    },
    {
        "url": "https://151l.shop/?pid=189512351",
        "untappd_url": "https://untappd.com/b/brasserie-knot-yamasachi/5211782",
        "gemini_update": {
            "brewery_name_en": "Brasserie Knot",
            "brewery_name_jp": "ブラッスリーノット",
            "beer_name_en": "YAMASACHI",
            "beer_name_jp": "ヤマサチ",
            "beer_name_core": "YAMASACHI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brasserie-knot-yamasachi/5211782"
        }
    },
    {
        "url": "https://151l.shop/?pid=189512381",
        "untappd_url": "https://untappd.com/b/brasserie-knot-keyaki/6413219",
        "gemini_update": {
            "brewery_name_en": "Brasserie Knot",
            "brewery_name_jp": "ブラッスリーノット",
            "beer_name_en": "KEYAKI",
            "beer_name_jp": "欅",
            "beer_name_core": "KEYAKI",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/brasserie-knot-keyaki/6413219"
        }
    },
    {
        "url": "https://151l.shop/?pid=194260364",
        "untappd_url": "https://untappd.com/b/rar-brewing-talking-to-trees-fruited/6490033",
        "gemini_update": {
            "brewery_name_en": "RaR Brewing x Tall Trees Brewery",
            "brewery_name_jp": "ラーブルーイング × トールツリーズ",
            "beer_name_en": "Talking To Trees Fruited",
            "beer_name_jp": "トーキングトゥツリーズ フルーテッド",
            "beer_name_core": "Talking To Trees",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rar-brewing-talking-to-trees-fruited/6490033"
        }
    },
    {
        "url": "https://maruho.shop/products/rolling-in-clouds-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-rolling-in-clouds/2928558",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Rolling In Clouds",
            "beer_name_jp": "ローリング・イン・クラウズ",
            "beer_name_core": "Rolling In Clouds",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-rolling-in-clouds/2928558"
        }
    },
    {
        "url": "https://maruho.shop/products/ploom-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-ploom/5529924",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Ploom",
            "beer_name_jp": "プルーム",
            "beer_name_core": "Ploom",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-ploom/5529924"
        }
    },
    {
        "url": "https://maruho.shop/products/doggo-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-doggo/4684921",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Doggo",
            "beer_name_jp": "ドッゴ",
            "beer_name_core": "Doggo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-doggo/4684921"
        }
    },
    {
        "url": "https://maruho.shop/products/finback-ipa-473ml-finback",
        "untappd_url": "https://untappd.com/b/finback-brewery-ipa/297346",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "IPA",
            "beer_name_jp": "フィンバックIPA",
            "beer_name_core": "Finback IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-ipa/297346"
        }
    },
    {
        "url": "https://151l.shop/?pid=194201565",
        "untappd_url": "https://untappd.com/b/vertere-achillea/6709616",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Achillea",
            "beer_name_jp": "アキレア",
            "beer_name_core": "Achillea",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-achillea/6709616"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060765",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Tahoe Deep",
            "beer_name_jp": "タホディープ",
            "beer_name_core": "Tahoe Deep",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194186421",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-simtra-triple-ipa/93848",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Simtra Triple IPA",
            "beer_name_jp": "シムトラ トリプル IPA",
            "beer_name_core": "Simtra",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-simtra-triple-ipa/93848"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194186419",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Tahoe Deep",
            "beer_name_jp": "タホディープ",
            "beer_name_core": "Tahoe Deep",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194186418",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-breaking-bud/929842",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Breaking Bud",
            "beer_name_jp": "ブレイキングバド",
            "beer_name_core": "Breaking Bud",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-breaking-bud/929842"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194169606",
        "untappd_url": "https://untappd.com/b/hudson-valley-brewery-planetfall/2202576",
        "gemini_update": {
            "brewery_name_en": "Hudson Valley Brewery",
            "brewery_name_jp": "ハドソンバレー",
            "beer_name_en": "Planetfall",
            "beer_name_jp": "プラネットフォール",
            "beer_name_core": "Planetfall",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hudson-valley-brewery-planetfall/2202576"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194169604",
        "untappd_url": "https://untappd.com/b/hudson-valley-brewery-soleil-sipa/2597723",
        "gemini_update": {
            "brewery_name_en": "Hudson Valley Brewery",
            "brewery_name_jp": "ハドソンバレー",
            "beer_name_en": "Soleil SIPA",
            "beer_name_jp": "ソレイユ SIPA",
            "beer_name_core": "Soleil",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hudson-valley-brewery-soleil-sipa/2597723"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194169601",
        "untappd_url": "https://untappd.com/b/hudson-valley-brewery-peach-silhouette/2323947",
        "gemini_update": {
            "brewery_name_en": "Hudson Valley Brewery",
            "brewery_name_jp": "ハドソンバレー",
            "beer_name_en": "Peach Silhouette",
            "beer_name_jp": "ピーチ シルエット",
            "beer_name_core": "Peach Silhouette",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hudson-valley-brewery-peach-silhouette/2323947"
        }
    },

    # --- Untappd未紐付け在庫ビールから調査特定 (5件) ---
    {
        "url": "https://151l.shop/?pid=193571646",
        "untappd_url": "https://untappd.com/b/isekado-kadolabo-041-marginal-vi/7655050",
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Kadolabo 041 Marginal VI",
            "beer_name_jp": "カドラボ041",
            "beer_name_core": "Kadolabo 041",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/isekado-kadolabo-041-marginal-vi/7655050"
        }
    },
    {
        "url": "https://151l.shop/?pid=194079981",
        "untappd_url": "https://untappd.com/b/vertere-cotinus/7652896",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Cotinus",
            "beer_name_jp": "コティヌス",
            "beer_name_core": "Cotinus",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-cotinus/7652896"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8167",
        "untappd_url": "https://untappd.com/b/be-easy-brewing-be-easy-dosa-yukkosa/7640062",
        "gemini_update": {
            "brewery_name_en": "Be Easy Brewing",
            "brewery_name_jp": "ビーイージーブルーイング",
            "beer_name_en": "Be Easy Dosa？Yukkosa! どさ！ゆっこさ！",
            "beer_name_jp": "どさ？ゆっこさ！",
            "beer_name_core": "Dosa?Yukkosa!",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/be-easy-brewing-be-easy-dosa-yukkosa/7640062"
        }
    },
    {
        "url": "https://151l.shop/?pid=194201540",
        "untappd_url": "https://untappd.com/b/vertere-vanitas/7648720",
        "gemini_update": {
            "brewery_name_en": "VERTERE × Kyoto Brewing Company",
            "brewery_name_jp": "バテレ × 京都醸造",
            "beer_name_en": "Vanitas",
            "beer_name_jp": "ヴァニタス",
            "beer_name_core": "Vanitas",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/vertere-vanitas/7648720"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=5993",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-hinterland-ipa/66598",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド",
            "beer_name_en": "Hinterland IPA",
            "beer_name_jp": "インディアペールエール",
            "beer_name_core": "Hinterland IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-hinterland-ipa/66598"
        }
    }
]

# 2. 未登録確認済みアイテム（今回はすべてUntappdが存在したためなし）
UNREGISTERED_INSPECTED_URLS = []

# 3. ローリング巡回・Untappd データの最新化対象（5件）
BEER_REFRESH_URLS = [
    "https://untappd.com/b/humble-sea-brewing-co-slipknautical/6756110",
    "https://untappd.com/b/rar-brewing-passing-peaks/6490020",
    "https://untappd.com/b/rar-brewing-waterman-jr/6491305",
    "https://untappd.com/b/nobody-brewing-the-triphop/6571279",
    "https://untappd.com/b/rar-brewing-out-of-order-pup-pouch/6486227"
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

    # 2. 未登録確認済みアイテムの調査タイムスタンプ更新
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

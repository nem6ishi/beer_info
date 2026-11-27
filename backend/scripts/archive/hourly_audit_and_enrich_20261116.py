import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 誤紐付け修正アイテム (Parageusia 13)
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://maruho.shop/products/parageusia-13-500ml-tired-hands",
        "name": "Parageusia 13 500ml/Tired Hands",
        "untappd_url": "https://untappd.com/b/tired-hands-brewing-company-paraguesia13/3259469",
        "gemini_update": {
            "brewery_name_en": "Tired Hands Brewing Company",
            "brewery_name_jp": "タイアードハンズ",
            "beer_name_en": "Paraguesia13",
            "beer_name_jp": "パラギュージャー13",
            "beer_name_core": "Parageusia 13",
            "search_hint": "Parageusia 13 Tired Hands Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tired-hands-brewing-company-paraguesia13/3259469"
        }
    },
    {
        "url": "https://151l.shop/?pid=173222788",
        "name": "タイアードハンズ　パラギュージャー13（Tired Hands Parageusia 13）",
        "untappd_url": "https://untappd.com/b/tired-hands-brewing-company-paraguesia13/3259469",
        "gemini_update": {
            "brewery_name_en": "Tired Hands Brewing Company",
            "brewery_name_jp": "タイアードハンズ",
            "beer_name_en": "Paraguesia13",
            "beer_name_jp": "パラギュージャー13",
            "beer_name_core": "Parageusia 13",
            "search_hint": "Parageusia 13 Tired Hands Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tired-hands-brewing-company-paraguesia13/3259469"
        }
    }
]

# 2. 新規エンリッチ & Untappd特定済み商品の登録
NEW_ENRICH_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=173883476",
        "name": "サイドプロジェクト / Side Project Saison du Fermier Pinot Noir Puncheons (Blend #4)",
        "untappd_url": "https://untappd.com/b/side-project-brewing-saison-du-fermier-from-pinot-noir-puncheons-blend-4/3625388",
        "gemini_update": {
            "brewery_name_en": "Side Project Brewing",
            "brewery_name_jp": "サイドプロジェクト",
            "beer_name_en": "Saison du Fermier from Pinot Noir Puncheons (Blend #4)",
            "beer_name_jp": "セゾン ド フェルミエ ピノノワール パンチョン (ブレンド #4)",
            "beer_name_core": "Saison du Fermier from Pinot Noir Puncheons",
            "search_hint": "Saison du Fermier from Pinot Noir Puncheons Blend #4 Side Project Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/side-project-brewing-saison-du-fermier-from-pinot-noir-puncheons-blend-4/3625388"
        }
    },
    {
        "url": "https://beervolta.com/?pid=172458699",
        "name": "スモッグシティー フレンチツイストウィズレモン&バニラ / Smog City French Twist w/Lemon & Vanilla",
        "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275",
        "gemini_update": {
            "brewery_name_en": "Smog City Brewing Co.",
            "brewery_name_jp": "スモッグシティ",
            "beer_name_en": "French Twist",
            "beer_name_jp": "フレンチ ツイスト",
            "beer_name_core": "French Twist",
            "search_hint": "French Twist Smog City Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b060-b50054",
        "name": "Smog City French Twist w/Lemon & Vanilla (500ml) / フレンチ ツイスト ウィズ レモン&バニラ",
        "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275",
        "gemini_update": {
            "brewery_name_en": "Smog City Brewing Co.",
            "brewery_name_jp": "スモッグシティ",
            "beer_name_en": "French Twist",
            "beer_name_jp": "フレンチ ツイスト",
            "beer_name_core": "French Twist",
            "search_hint": "French Twist Smog City Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275"
        }
    },
    {
        "url": "https://maruho.shop/products/french-twist-w-lemon-vanilla-500ml-smog-city",
        "name": "French Twist w/Lemon & Vanilla 500ml/Smog City",
        "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275",
        "gemini_update": {
            "brewery_name_en": "Smog City Brewing Co.",
            "brewery_name_jp": "スモッグシティ",
            "beer_name_en": "French Twist",
            "beer_name_jp": "フレンチ ツイスト",
            "beer_name_core": "French Twist",
            "search_hint": "French Twist Smog City Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275"
        }
    },
    {
        "url": "https://151l.shop/?pid=172482559",
        "name": "スモッグシティ　フレンチツイストレモン＆バニラ（Smog City French Twist w/Lemon & Vanilla）",
        "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275",
        "gemini_update": {
            "brewery_name_en": "Smog City Brewing Co.",
            "brewery_name_jp": "スモッグシティ",
            "beer_name_en": "French Twist",
            "beer_name_jp": "フレンチ ツイスト",
            "beer_name_core": "French Twist",
            "search_hint": "French Twist Smog City Brewing Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275"
        }
    },
    {
        "url": "https://beervolta.com/?pid=174180581",
        "name": "ネイベル シュルート / Nevel Gloed",
        "untappd_url": "https://untappd.com/b/nevel-gloed/2397621",
        "gemini_update": {
            "brewery_name_en": "Nevel",
            "brewery_name_jp": "ネイベル",
            "beer_name_en": "Gloed",
            "beer_name_jp": "シュルート",
            "beer_name_core": "Gloed",
            "search_hint": "Gloed Nevel",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/nevel-gloed/2397621"
        }
    },
    {
        "url": "https://beervolta.com/?pid=173884522",
        "name": "サイドプロジェクト / Side Project Tête de Cuvée (Vintage 2020)",
        "untappd_url": "https://untappd.com/b/side-project-brewing-tete-de-cuvee-vintage-2020/4980515",
        "gemini_update": {
            "brewery_name_en": "Side Project Brewing",
            "brewery_name_jp": "サイドプロジェクト",
            "beer_name_en": "Tête de Cuvée (Vintage 2020)",
            "beer_name_jp": "テート ド キュヴェ (ヴィンテージ 2020)",
            "beer_name_core": "Tête de Cuvée",
            "search_hint": "Tête de Cuvée Vintage 2020 Side Project Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/side-project-brewing-tete-de-cuvee-vintage-2020/4980515"
        }
    }
]

# 3. Untappd未登録商品の監査確認更新
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=173884556",
        "name": "サイドプロジェクト / Side Project Single Farm",
        "gemini_update": {
            "brewery_name_en": "Side Project Brewing",
            "brewery_name_jp": "サイドプロジェクト",
            "beer_name_en": "Single Farm",
            "beer_name_jp": "シングルファーム",
            "beer_name_core": "Single Farm",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    }
]

# 4. ローリング巡回・Untappd詳細取得＆更新対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/mahowbrew-dancing-in-the-moonlight/6407820",
    "https://untappd.com/b/la-brasserie-du-mont-saleve-tzarine-imperial-stout-9/338460",
    "https://untappd.com/b/tired-hands-brewing-company-paraguesia13/3259469",
    "https://untappd.com/b/side-project-brewing-saison-du-fermier-from-pinot-noir-puncheons-blend-4/3625388",
    "https://untappd.com/b/smog-city-brewing-co-french-twist/4157275",
    "https://untappd.com/b/nevel-gloed/2397621",
    "https://untappd.com/b/side-project-brewing-tete-de-cuvee-vintage-2020/4980515"
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
    logger.info(f"\n[4] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} audit beers...")
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

import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ & Untappd特定済み商品の登録
NEW_ENRICH_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/hop-chan-is-back",
        "name": "[AMAKUSA SONAR BEER] HOP chan is BACK/ ホップちゃん イズ バック",
        "untappd_url": "https://untappd.com/b/amakusa-sonar-beer/7666837",
        "gemini_update": {
            "brewery_name_en": "AMAKUSA SONAR BEER",
            "brewery_name_jp": "天草ソナービール",
            "beer_name_en": "HOP chan is BACK",
            "beer_name_jp": "ホップちゃん イズ バック",
            "beer_name_core": "HOP chan is BACK",
            "search_hint": "HOP chan AMAKUSA SONAR BEER",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/amakusa-sonar-beer/7666837"
        }
    },
    {
        "url": "https://beervolta.com/?pid=178519418",
        "name": "エコーズ モンクズインディスクレション / Echoes Monk's Indiscretion",
        "untappd_url": "https://untappd.com/b/echoes-brewing-company-monk-s-indiscretion/4256701",
        "gemini_update": {
            "brewery_name_en": "Echoes Brewing Company",
            "brewery_name_jp": "エコーズ",
            "beer_name_en": "Monk's Indiscretion",
            "beer_name_jp": "モンクズインディスクレション",
            "beer_name_core": "Monk's Indiscretion",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/echoes-brewing-company-monk-s-indiscretion/4256701"
        }
    }
]

# 2. Untappd未登録商品の監査確認更新（次回以降の巡回間隔調整）
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/maelstrom-hazy-ipa",
        "name": "[GAME BREW] 魔海侯フォルネウス MAELSTROM HAZY IPA  / メイルストローム ヘイジーIPA",
        "gemini_update": {
            "brewery_name_en": "Game Brew",
            "brewery_name_jp": "ゲームブリュー",
            "beer_name_en": "Maelstrom Hazy IPA",
            "beer_name_jp": "魔海侯フォルネウス メイルストローム ヘイジーIPA",
            "beer_name_core": "Maelstrom Hazy IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/buchikamashi-helles",
        "name": "[GAME BREW] 魔戦士公 アラケス BUCHIKAMASHI HELLES / ブチカマシ ヘレス",
        "gemini_update": {
            "brewery_name_en": "Game Brew",
            "brewery_name_jp": "ゲームブリュー",
            "beer_name_en": "Buchikamashi Helles",
            "beer_name_jp": "魔戦士公 アラケス ブチカマシ ヘレス",
            "beer_name_core": "Buchikamashi Helles",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/heat-wave-ipa",
        "name": "[GAME BREW] 魔炎長 アウナス HEAT WAVE IPA / ヒートウェイブ IPA",
        "gemini_update": {
            "brewery_name_en": "Game Brew",
            "brewery_name_jp": "ゲームブリュー",
            "beer_name_en": "Heat Wave IPA",
            "beer_name_jp": "魔炎長 アウナス ヒートウェイブ IPA",
            "beer_name_core": "Heat Wave IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    }
]

# 3. ローリング巡回・Untappd詳細取得＆更新対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/evil-twin-brewing-nyc-corner-of-george-st-and-shawmut-road/3267520",
    "https://untappd.com/b/cellarmaker-brewing-company-double-dobis/840252",
    "https://untappd.com/b/brouwerij-3-fonteinen-3-fonteinen-x-christoph-hoch-druif-gruner-veltliner-season-22-23-blend-no-38/5471951",
    "https://untappd.com/b/soma-beer-origin/6619749"
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

    # 1. 新規エンリッチの登録
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

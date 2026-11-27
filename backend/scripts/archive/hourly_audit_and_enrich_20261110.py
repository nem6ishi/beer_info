import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 非ビール商品の分類更新（グラス・グッズ等）
NON_BEER_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=188139331",
        "name": "トリリウム クージー 深緑 / Trillium Koozie Deep Green",
        "gemini_update": {
            "brewery_name_en": "Trillium Brewing Company",
            "brewery_name_jp": "トリリウム",
            "beer_name_en": "Koozie Deep Green",
            "beer_name_jp": "クージー 深緑",
            "beer_name_core": "Koozie",
            "product_type": "other",
            "is_set": False,
            "untappd_url": None
        }
    },
    {
        "url": "https://beervolta.com/?pid=192055841",
        "name": "ストーン パイントグラス / Stone Pint Glass",
        "gemini_update": {
            "brewery_name_en": "Stone Brewing",
            "brewery_name_jp": "ストーン",
            "beer_name_en": "Pint Glass",
            "beer_name_jp": "パイントグラス",
            "beer_name_core": "Pint Glass",
            "product_type": "glass",
            "is_set": False,
            "untappd_url": None
        }
    }
]

# 2. 新規エンリッチ & 未紐付け特定商品の登録（ミード・サイダー等）
NEW_ENRICH_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=157274359",
        "name": "シュラムズ ミード / Schramm's Mead A Smile Of Fortune",
        "untappd_url": "https://untappd.com/b/schramm-s-mead-a-smile-of-fortune/1678638",
        "gemini_update": {
            "brewery_name_en": "Schramm's Mead",
            "brewery_name_jp": "シュラムズ ミード",
            "beer_name_en": "A Smile of Fortune",
            "beer_name_jp": "スマイル オブ フォーチュン",
            "beer_name_core": "A Smile of Fortune",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/schramm-s-mead-a-smile-of-fortune/1678638"
        }
    },
    {
        "url": "https://beervolta.com/?pid=191462161",
        "name": "トゥーミータートール : ヒューオン ファームハウス ワイルド ドライ サイダー | Two Metre Tall: 2019-20 Huon Farmhouse Wild Cider",
        "untappd_url": "https://untappd.com/b/two-metre-tall-huon-wild-farmhouse-cider-2019-20-and-21/5587186",
        "gemini_update": {
            "brewery_name_en": "Two Metre Tall",
            "brewery_name_jp": "トゥーミータートール",
            "beer_name_en": "2019-20 Huon Farmhouse Wild Cider",
            "beer_name_jp": "ヒューオン ファームハウス ワイルド ドライ サイダー",
            "beer_name_core": "Huon Farmhouse Wild Cider",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/two-metre-tall-huon-wild-farmhouse-cider-2019-20-and-21/5587186"
        }
    }
]

# 3. Untappd未登録商品の監査確認更新
UNREGISTERED_BEER_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=193866863",
        "name": "セッションズ : はっさくスマッシュ | Session's: Hassaku Smash",
        "gemini_update": {
            "brewery_name_en": "Session's Brewery",
            "brewery_name_jp": "セッションズ",
            "beer_name_en": "Hassaku Smash",
            "beer_name_jp": "はっさくスマッシュ",
            "beer_name_core": "Hassaku Smash",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": None
        }
    }
]

# 4. 誤紐付けの是正アイテム
CORRECTION_ITEMS = [
    {
        "url": "https://beervolta.com/?pid=190676874",
        "name": "トラップドア x フォートジョージ : シークレット ハンドシェイク | Trap Door x Fort George: Secret Handshake",
        "untappd_url": "https://untappd.com/b/trap-door-brewing-secret-handshake/6505305",
        "gemini_update": {
            "brewery_name_en": "Trap Door Brewing",
            "brewery_name_jp": "トラップドア",
            "beer_name_en": "Secret Handshake",
            "beer_name_jp": "シークレット ハンドシェイク",
            "beer_name_core": "Secret Handshake",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/trap-door-brewing-secret-handshake/6505305"
        }
    },
    {
        "url": "https://beervolta.com/?pid=174203047",
        "name": "ボエレネルフ エイレンボッシュ オードスカルベーク クリーク / Het Boerenerf Eylenbosch Oude Schaarbeekse Kriek Oogast 2020 750ml",
        "untappd_url": "https://untappd.com/b/het-boerenerf-eylenbosch-schaarbeekse-kriek-oogst-2020/4366722",
        "gemini_update": {
            "brewery_name_en": "Het Boerenerf Eylenbosch",
            "brewery_name_jp": "ボエレネルフ エイレンボッシュ",
            "beer_name_en": "Schaarbeekse Kriek (Oogst 2020)",
            "beer_name_jp": "オードスカルベーク クリーク",
            "beer_name_core": "Schaarbeekse Kriek",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/het-boerenerf-eylenbosch-schaarbeekse-kriek-oogst-2020/4366722"
        }
    }
]

# 5. ローリング巡回・Untappd詳細取得＆更新対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/vatten-brewing-golden-pig/7664029",
    "https://untappd.com/b/bissell-brothers-brewing-company-resurrection-bourbon-and-rye-barrel/5493028",
    "https://untappd.com/b/nevel-fors/4770323"
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

    # 1. 非ビール商品（グッズ・グラス）の修正
    logger.info(f"\n[1] Updating {len(NON_BEER_ITEMS)} non-beer items (goods/glasses)...")
    for item in NON_BEER_ITEMS:
        url = item["url"]
        gem_update = item["gemini_update"]
        logger.info(f"  Fixing non-beer: {item['name']} -> {gem_update['product_type']}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert(gem_update, on_conflict="url")))

        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": None,
            "untappd_enriched_at": now_iso
        }).eq("url", url)))

    # 2. 新規エンリッチ（ミード・サイダー等）の登録
    logger.info(f"\n[2] Enriching {len(NEW_ENRICH_ITEMS)} target beverage items...")
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

    # 4. 誤紐付けの是正
    logger.info(f"\n[4] Correcting {len(CORRECTION_ITEMS)} mismatched items...")
    for item in CORRECTION_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"  Correcting {url} -> {untappd_url}")

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
            logger.info(f"  ✅ Corrected & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

    # 5. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[5] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
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

    # 6. マテリアライズドビューのリフレッシュ
    logger.info("\n[6] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

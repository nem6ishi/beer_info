import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 誤紐付け・メタデータ是正 + 横展開アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        # scraped_beers は 2026 (6999000) だったが gemini_data が 2025 (6432570) のままだったため是正
        "url": "https://www.arome.jp/products/detail.php?product_id=2592",
        "name": "フリモント / ヘッドフルオブフレッシュホップス (2026) (Fresh Hop Hazy IPA) 473ml缶 [Fremont Brewing / Head Full of Fresh Hops (2026)]",
        "untappd_url": "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
        "gemini_update": {
            "brewery_name_en": "Fremont Brewing",
            "brewery_name_jp": "フリモント",
            "beer_name_en": "Head Full of Fresh Hops (2026)",
            "beer_name_jp": "ヘッドフルオブフレッシュホップス",
            "beer_name_core": "Head Full of Fresh Hops",
            "search_hint": "Head Full of Fresh Hops 2026 Fremont Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
        },
    },
    {
        # scraped_beers は 2026 (7009515) だったが gemini_data が無印 (6953) のままだったため是正
        "url": "https://www.antenna-america.com/products/b036-b37134",
        "name": "The Bruery Black Tuesday 2026 (入数12) (375ml) / ブラック チューズデー【11/19出荷】",
        "untappd_url": "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
        "gemini_update": {
            "brewery_name_en": "The Bruery",
            "brewery_name_jp": None,
            "beer_name_en": "Black Tuesday (2026)",
            "beer_name_jp": "ブラック チューズデー",
            "beer_name_core": "Black Tuesday",
            "search_hint": "Black Tuesday 2026 The Bruery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
        },
    },
    {
        # 横展開: アロームの同商品ページが 2026年11月20日入荷 (6回目・6.0%・IBU54) に更新されているため 2026年版へ是正
        "url": "https://www.arome.jp/products/detail.php?product_id=3055",
        "name": "志賀高原ビール / ホッピーブラウン・ゴーズアップ (Brown Ale / IPA) 330ml瓶 [Shiga Kogen Beer / Hoppy Brown Goes Up]",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-hoppy-brown-goes-up-2026/7650621",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Shiga Kogen Hoppy Brown Goes Up (2026)",
            "beer_name_jp": "ホッピーブラウン・ゴーズアップ",
            "beer_name_core": "Hoppy Brown Goes Up",
            "search_hint": "Shiga Kogen Hoppy Brown Goes Up 2026 Tamamura Honten",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-hoppy-brown-goes-up-2026/7650621",
        },
    },
]

# 2. Untappd未紐付け在庫ビールから新規特定 (2件)
NEW_ENRICH_ITEMS = [
    {
        "url": "https://www.antenna-america.com/products/b015-c16004",
        "name": "Coronado Nado Premium Lager (473ml) / ナド",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-nado/5009174",
        "gemini_update": {
            "brewery_name_en": "Coronado Brewing Company",
            "brewery_name_jp": "コロナド",
            "beer_name_en": "Nado",
            "beer_name_jp": "ナド",
            "beer_name_core": "Nado",
            "search_hint": "Nado Coronado Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/coronado-brewing-company-nado/5009174",
        },
    },
    {
        "url": "https://151l.shop/?pid=194510735",
        "name": "【11/20（金）予定・めっちゃ美味しいので再入荷！】志賀高原ビール　ホッピーブラウンゴーズアップ（SHIGA KOGEN Hoppy Brown Goes Up）",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-hoppy-brown-goes-up-2026/7650621",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Shiga Kogen Hoppy Brown Goes Up (2026)",
            "beer_name_jp": "ホッピーブラウンゴーズアップ",
            "beer_name_core": "Hoppy Brown Goes Up",
            "search_hint": "Shiga Kogen Hoppy Brown Goes Up 2026 Tamamura Honten",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-shiga-kogen-hoppy-brown-goes-up-2026/7650621",
        },
    },
]

# 3. Untappd未登録確認済みアイテム (調査日時のみ更新)
UNLINKED_CHECKED_URLS = [
    "https://151l.shop/?pid=193631430",  # FARMENTRY お茶！大和 (OCHA! YAMATO) - Longjingは登録あるがYAMATOは未登録
    "https://witchcraftmarket.com/products/buchikamashi-helles",  # GAME BREW 魔戦士公 アラケス BUCHIKAMASHI HELLES - Untappd未登録
    "https://witchcraftmarket.com/products/trinity-blaster-pale-ale",  # GAME BREW 魔龍公 ビューネイ TRINITY BLASTER PALE ALE - Untappd未登録
]

# 4. Untappd詳細取得・最新化対象 (新規特定 + ローリング巡回監査 + 直近確認)
BEER_REFRESH_URLS = [
    # 新規特定 (2件)
    "https://untappd.com/b/coronado-brewing-company-nado/5009174",
    "https://untappd.com/b/tamamura-honten-co-shiga-kogen-hoppy-brown-goes-up-2026/7650621",
    # ローリング巡回監査 (5件)
    "https://untappd.com/b/craft-beer-base-hahaha-golden-ale/6421677",
    "https://untappd.com/b/and-beer-hops/6685692",
    "https://untappd.com/b/isekado/6910970",
    "https://untappd.com/b/lumen-beer-co-full-noise/6608026",
    "https://untappd.com/b/game-brew-cool-like-dat/6817174",
    # 直近確認対象 (5件も最新化)
    "https://untappd.com/b/smog-city-brewing-co-amarilla-gorilla/295203",
    "https://untappd.com/b/fremont-brewing-head-full-of-fresh-hops-2026/6999000",
    "https://untappd.com/b/topa-topa-brewing-co-chief-peak-ipa/1117720",
    "https://untappd.com/b/the-bruery-black-tuesday-2026/7009515",
    "https://untappd.com/b/gueuzerie-tilquin-oude-rhubarbe-tilquin-a-l-ancienne-2021-2022/4788026",
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

    # 1. 誤紐付け・メタデータ是正
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} items...")
    for item in FIX_MISASSIGNED_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])

        logger.info(f"  Fixing {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))

        run_db_op(lambda u=url, uu=untappd_url: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": uu,
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 2. 未紐付け特定商品のエンリッチ登録
    logger.info(f"\n[2] Enriching {len(NEW_ENRICH_ITEMS)} items...")
    for item in NEW_ENRICH_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])

        logger.info(f"  Enriching {url} -> {untappd_url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))

        run_db_op(lambda u=url, uu=untappd_url: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": uu,
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 3. Untappd未登録ビール調査済みマーク更新
    logger.info(f"\n[3] Updating investigation timestamp for {len(UNLINKED_CHECKED_URLS)} unlinked beers...")
    for url in UNLINKED_CHECKED_URLS:
        logger.info(f"  Checked (unlinked on Untappd): {url}")
        run_db_op(lambda u=url: sync_execute(sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 4. Untappd データの詳細取得・最新化
    logger.info(f"\n[4] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda p=payload: sync_execute(sb.table("untappd_data").upsert(p, on_conflict="untappd_url")))
            logger.info(
                f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} "
                f"| Style: {details.get('untappd_style')} | ABV: {details.get('untappd_abv')} "
                f"| Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}"
            )
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.5)

    await close_async_client()

    # 5. マテリアライズドビューのリフレッシュ
    logger.info("\n[5] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")


if __name__ == "__main__":
    asyncio.run(main())

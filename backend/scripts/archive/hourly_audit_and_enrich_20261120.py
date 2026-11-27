import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. ローリング監査 誤紐付け是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6610",
        "name": "セラドアエールズ / ヴァイン・オブ・ザ・デッド (Rustic Wild Ale w/ Cabernet & Charbono Skins) 500ml瓶 [Cellador Ales / Vine of the Dead]",
        "untappd_url": "https://untappd.com/b/cellador-ales-vine-of-the-dead-2022-packaged-dec-2021/4732247",
        "gemini_update": {
            "brewery_name_en": "Cellador Ales",
            "brewery_name_jp": "セラドアエールズ",
            "beer_name_en": "Vine of the Dead '2022' (Packaged Dec 2021)",
            "beer_name_jp": "ヴァイン・オブ・ザ・デッド",
            "beer_name_core": "Vine of the Dead",
            "search_hint": "Vine of the Dead 2022 Cabernet Charbono Cellador Ales",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/cellador-ales-vine-of-the-dead-2022-packaged-dec-2021/4732247",
        },
    },
]

# 2. 未エンリッチ商品 (最優先) + Untappd未紐付け在庫ビール (特定済み登録)
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (4件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=2164",
        "name": "フリモント / ザ・ラスティネイル 2026 (Bourbon Barrel Aged Imperial Stout) 650ml瓶 [Fremont Brewing / The Rusty Nail 2026]",
        "untappd_url": "https://untappd.com/b/fremont-brewing-the-rusty-nail-2026/6750086",
        "gemini_update": {
            "brewery_name_en": "Fremont Brewing",
            "brewery_name_jp": "フリモント",
            "beer_name_en": "The Rusty Nail (2026)",
            "beer_name_jp": "ザ・ラスティネイル 2026",
            "beer_name_core": "The Rusty Nail",
            "search_hint": "The Rusty Nail 2026 Fremont Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/fremont-brewing-the-rusty-nail-2026/6750086",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194522452",
        "name": "ウェストコースト : ザ ゲートウェイ | West Coast (WCB): The Gateway",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-the-gateway/4515252",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウェストコースト",
            "beer_name_en": "The Gateway",
            "beer_name_jp": "ザ ゲートウェイ",
            "beer_name_core": "The Gateway",
            "search_hint": "The Gateway West Coast Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-the-gateway/4515252",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194522451",
        "name": "ウェストコースト : ホップ シェフ | West Coast (WCB): Hop Chef",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-hop-chef/7682882",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウェストコースト",
            "beer_name_en": "Hop Chef",
            "beer_name_jp": "ホップ シェフ",
            "beer_name_core": "Hop Chef",
            "search_hint": "Hop Chef West Coast Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-hop-chef/7682882",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194522403",
        "name": "うちゅう : 宇宙FLASH | Uchu: FLASH",
        "untappd_url": "https://untappd.com/b/uchu-brewing-flash-uchu-flash/6170813",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙FLASH (UCHU FLASH)",
            "beer_name_jp": "宇宙FLASH",
            "beer_name_core": "UCHU FLASH",
            "search_hint": "宇宙FLASH UCHU FLASH Uchu Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-flash-uchu-flash/6170813",
        },
    },
    # --- Untappd未紐付け在庫ビール (特定済み登録 2件) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6226",
        "name": "玉村本店 / 木樽熟成 山伏 b3 miyama #004 (Barrel Aged Farmhouse Ale) 750ml瓶 [Tamamura Honten / Barrel Aged Yama-Bushi b3 miyama -baby blonde brett miyama-]",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "玉村本店",
            "beer_name_en": "Barrel Aged Yama-Bushi B³ Miyama (Baby Blonde Brett Miyama) #004",
            "beer_name_jp": "木樽熟成 山伏 b3 miyama #004",
            "beer_name_core": "Barrel Aged Yama-Bushi b3 miyama",
            "search_hint": "Barrel Aged Yama-Bushi b3 miyama 004 Tamamura Honten",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003452",
        "name": "【ゆらゆらハードサイダー モスコサイダー/REC CIDER BEER WORKS】",
        "untappd_url": "https://untappd.com/b/rec-cider-beer-works-yura-yura-hard-cider-moscow-mule-cider/6375988",
        "gemini_update": {
            "brewery_name_en": "REC Cider Beer Works",
            "brewery_name_jp": "レックサイダー",
            "beer_name_en": "Yura Yura Hard Cider Moscow Mule Cider",
            "beer_name_jp": "ゆらゆらハードサイダー モスコサイダー",
            "beer_name_core": "Yura Yura Hard Cider Moscow Mule Cider",
            "search_hint": "Yura Yura Hard Cider Moscow Mule Cider REC Cider Beer Works",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rec-cider-beer-works-yura-yura-hard-cider-moscow-mule-cider/6375988",
        },
    },
]

# 3. Untappd未登録確認済みアイテム (調査日時のみ更新)
UNLINKED_CHECKED_URLS = [
    "https://beer-chouseiya.shop/shopdetail/000000003442",  # 豊穣日和'26-セゾン編-/Kankiku (Untappdは'25まで)
    "https://beer-chouseiya.shop/shopdetail/000000000860",  # 豊穣日和'26-ラガー編-/Kankiku (Untappdは'25まで)
    "https://witchcraftmarket.com/products/trinity-blaster-pale-ale",  # [GAME BREW] 魔龍公 ビューネイ (Untappd未登録)
]

# 4. Untappd詳細取得・最新化対象 (新規・是正・ローリング対象)
BEER_REFRESH_URLS = [
    # 新規 & 未紐付け特定
    "https://untappd.com/b/fremont-brewing-the-rusty-nail-2026/6750086",
    "https://untappd.com/b/west-coast-brewing-the-gateway/4515252",
    "https://untappd.com/b/west-coast-brewing-hop-chef/7682882",
    "https://untappd.com/b/uchu-brewing-flash-uchu-flash/6170813",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
    "https://untappd.com/b/rec-cider-beer-works-yura-yura-hard-cider-moscow-mule-cider/6375988",
    # 是正対象
    "https://untappd.com/b/cellador-ales-vine-of-the-dead-2022-packaged-dec-2021/4732247",
    # ローリング巡回監査 (残り4件)
    "https://untappd.com/b/baeren-bier-chocolate-stout-vintage-2026/6651073",
    "https://untappd.com/b/brasserie-de-la-senne-brett-saison/5900189",
    "https://untappd.com/b/brasserie-de-la-senne-zinnebir/50",
    "https://untappd.com/b/rikri-brewing-hollyfield/6832719",
    # 直近エンリッチ確認対象 (評価数更新確認)
    "https://untappd.com/b/totopia-brewery-zonephobia/7681240",
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
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned/mismatched beer items...")
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

    # 2. 新規・未紐付け特定商品のエンリッチ登録
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
        logger.info(f"  Checked (still unlinked on Untappd): {url}")
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

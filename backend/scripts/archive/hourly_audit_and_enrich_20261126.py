import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 直近追加商品の誤紐付け・メタデータ是正
FIX_MISASSIGNED_ITEMS = [
    {
        # マルホ酒店の Fear Addicted は商品説明に「Citra, Riwaka, Nelson」「賞味期限:2027/10/14」とあり、
        # 2024年過去レシピ(6026900: Citra and '24 Galaxy)ではなく他店と同じ 2026年版(7187613)が正当
        "url": "https://maruho.shop/products/fear-addicted-473ml-lyric",
        "name": "Fear Addicted 473ml/Lyric",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Fear Addicted (2026)",
            "beer_name_jp": "フィアー・アディクテッド",
            "beer_name_core": "Fear Addicted",
            "search_hint": "Fear Addicted 2026 Lyric Brewing Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
        },
    },
]

# 2. Untappd未紐付け在庫ビール新規特定 + 横展開
NEW_ENRICH_ITEMS = [
    {
        # マルホ酒店の説明文（500Lオークの大樽で14ヶ月熟成後、瓶内再発酵・約2ヶ月瓶熟成）が #004 (7671343) と完全一致
        "url": "https://maruho.shop/products/山伏-木樽熟成-b3-miyama-750ml-志賀高原ビール",
        "name": "山伏 木樽熟成 b3 miyama 750ml/志賀高原ビール",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Barrel Aged Yama-Bushi B³ Miyama (Baby Blonde Brett Miyama) #004",
            "beer_name_jp": "山伏 木樽熟成 b3 miyama #004",
            "beer_name_core": "Barrel Aged Yama-Bushi b3 Miyama",
            "search_hint": "Barrel Aged Yama-Bushi b3 Miyama #004 Tamamura Honten",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
        },
    },
    {
        # 横展開: BEER VOLTA の同 #004 未紐付けレコードも併せて紐付け
        "url": "https://beervolta.com/?pid=194522360",
        "name": "志賀高原 : 山伏 b3 ミヤマ004 | Shiga Kogen: b3 miyama -baby blonde brett miyama- #004",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Barrel Aged Yama-Bushi B³ Miyama (Baby Blonde Brett Miyama) #004",
            "beer_name_jp": "山伏 b3 ミヤマ004",
            "beer_name_core": "Barrel Aged Yama-Bushi b3 Miyama",
            "search_hint": "Barrel Aged Yama-Bushi b3 Miyama #004 Tamamura Honten",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
        },
    },
]

# 3. Untappd未登録・バリアント特定不可確認済みアイテム (調査日時のみ更新)
UNLINKED_CHECKED_URLS = [
    "https://beer-chouseiya.shop/shopdetail/000000003468",  # 【バーレイワイン8/丹波路ブルワリー】 (UntappdはBerley Wine, 3, 4のみで8は未登録)
    "https://beer-chouseiya.shop/shopdetail/000000003467",  # 【ヴァイツェン9/丹波路ブルワリー】 (9周年記念ヴァイツェンはUntappd未登録)
    "https://beer-chouseiya.shop/shopdetail/000000002921",  # 【八郷 秋あがり/大山Gビール】 (2025/2026年版未登録)
    "https://beervolta.com/?pid=173884556",                 # サイドプロジェクト / Side Project Single Farm (ホップバリアント未記載のため特定不可)
]

# 4. Untappd詳細取得・最新化対象 (是正・新規特定・ローリング巡回監査・直近確認)
BEER_REFRESH_URLS = [
    # 是正・新規特定 (2銘柄)
    "https://untappd.com/b/lyric-brewing-company-fear-addicted-2026/7187613",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-b3-miyama-baby-blonde-brett-miyama-004/7671343",
    # 10:25時点 ローリング巡回監査 + 直近確認 (7銘柄)
    "https://untappd.com/b/field-ales-field-saison/6628005",
    "https://untappd.com/b/smog-city-brewing-co-space-weather/4577726",
    "https://untappd.com/b/smog-city-brewing-co-smoke-m-if-ya-got-em/4267854",
    "https://untappd.com/b/field-ales-pipi/7697038",
    "https://untappd.com/b/totopia-brewery-solmphilia/7693300",
    "https://untappd.com/b/amaku-uku-okaeri-2026/7693243",
    "https://untappd.com/b/smog-city-brewing-co-second-nature/6837115",
    # 12:54時点 ローリング巡回監査 + 直近確認 (9銘柄)
    "https://untappd.com/b/ambitious-ales-central-perk/1143011",
    "https://untappd.com/b/sierra-nevada-brewing-co-mango-little-thing/6705171",
    "https://untappd.com/b/harland-brewing-company-90-mile-haze/6659059",
    "https://untappd.com/b/foam-brewers-experimental-jet-set/2113626",
    "https://untappd.com/b/tree-house-brewing-company-blender-king/4718613",
    "https://untappd.com/b/ambitious-ales-gandalf-the-crisp/3330280",
    "https://untappd.com/b/deschutes-brewery-tropical-fresh/4950588",
    "https://untappd.com/b/ambitious-ales-professional-human-being/3841256",
    "https://untappd.com/b/deschutes-brewery-king-crispy-pilsner/3527234",
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
    logger.info(f"\n[1] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned items...")
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

    # 3. Untappd未登録・特定不可ビール調査済みマーク更新
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

import asyncio
import logging
import time
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.services.untappd.http_client import scrape_beer_details, close_async_client
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 非ビール商品の分類更新（芋焼酎など）
NON_BEER_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/witch-of-ozu-1",
        "name": "WITCH OF OZU / ウィッチ オブ オオズ",
        "gemini_update": {
            "brewery_name_en": "WITCH CRAFT MARKET",
            "brewery_name_jp": "WITCH CRAFT MARKET",
            "beer_name_en": "WITCH OF OZU",
            "beer_name_jp": "ウィッチ オブ オオズ",
            "beer_name_core": "WITCH OF OZU",
            "search_hint": "WITCH OF OZU Shochu",
            "product_type": "other",
            "is_set": False,
            "untappd_url": None,
        },
    },
]

# 2. 直近追加商品の誤紐付け・メタデータ是正アイテム
FIX_MISASSIGNED_ITEMS = [
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000011",
        "name": "【PALE ALE/Harvest Moon】",
        "untappd_url": "https://untappd.com/b/ikspiari-co-harvestmoon-pale-ale/98597",
        "gemini_update": {
            "brewery_name_en": "IKSPIARI Co.",
            "brewery_name_jp": "ハーヴェスト・ムーン",
            "beer_name_en": "Harvestmoon Pale Ale",
            "beer_name_jp": "ペールエール",
            "beer_name_core": "Pale Ale",
            "search_hint": "Harvestmoon Pale Ale IKSPIARI Co.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/ikspiari-co-harvestmoon-pale-ale/98597",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000448",
        "name": "【India Pale Ale/南信州】",
        "untappd_url": "https://untappd.com/b/minamishinshu-beer-ogna-india-pale-ale/5027734",
        "gemini_update": {
            "brewery_name_en": "Minamishinshu Beer (南信州ビール)",
            "brewery_name_jp": "南信州ビール",
            "beer_name_en": "Ogna INDIA PALE ALE",
            "beer_name_jp": "India Pale Ale",
            "beer_name_core": "India Pale Ale",
            "search_hint": "Ogna INDIA PALE ALE Minamishinshu Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/minamishinshu-beer-ogna-india-pale-ale/5027734",
        },
    },
]

# 3. 未エンリッチ商品 (最優先 13件) + Untappd未紐付け在庫ビール (新規特定 1件)
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (13件) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003471",
        "name": "【宇宙BREAK3/うちゅう】",
        "untappd_url": "https://untappd.com/b/uchu-brewing-break3-uchu-break3/7682783",
        "gemini_update": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "宇宙BREAK3 (UCHU BREAK3)",
            "beer_name_jp": "宇宙BREAK3",
            "beer_name_core": "宇宙BREAK3",
            "search_hint": "UCHU BREAK3 Uchu Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/uchu-brewing-break3-uchu-break3/7682783",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003470",
        "name": "【山椒のエール/丹波路ブルワリー】",
        "untappd_url": "https://untappd.com/b/tambaji-brewery-sansho-no-ale/3500096",
        "gemini_update": {
            "brewery_name_en": "Tambaji Brewery",
            "brewery_name_jp": "丹波路ブルワリー",
            "beer_name_en": "Sansho No Ale(山椒のを)",
            "beer_name_jp": "山椒のエール",
            "beer_name_core": "Sansho No Ale",
            "search_hint": "Sansho No Ale Tambaji Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tambaji-brewery-sansho-no-ale/3500096",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003466",
        "name": "【スモークエール/丹波路ブルワリー】",
        "untappd_url": "https://untappd.com/b/tambaji-brewery-smoke-ale/2672132",
        "gemini_update": {
            "brewery_name_en": "Tambaji Brewery",
            "brewery_name_jp": "丹波路ブルワリー",
            "beer_name_en": "Smoke Ale",
            "beer_name_jp": "スモークエール",
            "beer_name_core": "Smoke Ale",
            "search_hint": "Smoke Ale Tambaji Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tambaji-brewery-smoke-ale/2672132",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003465",
        "name": "【丹波うめサワー/丹波路ブルワリー】",
        "untappd_url": "https://untappd.com/b/tambaji-brewery-tamba-ume-sour/6565386",
        "gemini_update": {
            "brewery_name_en": "Tambaji Brewery",
            "brewery_name_jp": "丹波路ブルワリー",
            "beer_name_en": "Tamba Ume Sour",
            "beer_name_jp": "丹波うめサワー",
            "beer_name_core": "Tamba Ume Sour",
            "search_hint": "Tamba Ume Sour Tambaji Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tambaji-brewery-tamba-ume-sour/6565386",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003464",
        "name": "【丹波チェストナットエール/丹波路ブルワリー】",
        "untappd_url": "https://untappd.com/b/tambaji-brewery-tamba-chestnut-ale/2428023",
        "gemini_update": {
            "brewery_name_en": "Tambaji Brewery",
            "brewery_name_jp": "丹波路ブルワリー",
            "beer_name_en": "Tamba Chestnut Ale",
            "beer_name_jp": "丹波チェストナットエール",
            "beer_name_core": "Tamba Chestnut Ale",
            "search_hint": "Tamba Chestnut Ale Tambaji Brewery",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/tambaji-brewery-tamba-chestnut-ale/2428023",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003463",
        "name": "【Hop Chef/WestCoast】",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-hop-chef/7682882",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Hop Chef",
            "beer_name_jp": "Hop Chef",
            "beer_name_core": "Hop Chef",
            "search_hint": "Hop Chef West Coast Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-hop-chef/7682882",
        },
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003462",
        "name": "【Marzen/WestCoast】",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-marzen/7682881",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Marzen",
            "beer_name_jp": "Marzen",
            "beer_name_core": "Marzen",
            "search_hint": "Marzen West Coast Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/west-coast-brewing-marzen/7682881",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573867",
        "name": "テスト x ラー : ミュージック オブ ザ スフィアーズ | TEST x RaR: Music of the Spheres",
        "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "テスト",
            "beer_name_en": "Music of the Spheres",
            "beer_name_jp": "ミュージック オブ ザ スフィアーズ",
            "beer_name_core": "Music of the Spheres",
            "search_hint": "Music of the Spheres TEST",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573866",
        "name": "テスト x イーヴルツイン : チケッツ トゥ ザ サンセット | TEST x Evil Twin: Tickets To the Sunset",
        "untappd_url": "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "テスト",
            "beer_name_en": "Tickets To the Sunset",
            "beer_name_jp": "チケッツ トゥ ザ サンセット",
            "beer_name_core": "Tickets To the Sunset",
            "search_hint": "Tickets To the Sunset TEST",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573853",
        "name": "シングルヒル : ファイブ シスターズ (2026) | Single Hill: Five Sisters (2026)",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-five-sisters-2026/6961657",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Five Sisters (2026)",
            "beer_name_jp": "ファイブ シスターズ (2026)",
            "beer_name_core": "Five Sisters",
            "search_hint": "Five Sisters 2026 Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-five-sisters-2026/6961657",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573851",
        "name": "シングルヒル : ダンクマスター フラッシュ | Single Hill: Dankmaster Flash",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-dankmaster-flash/6390587",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Dankmaster Flash",
            "beer_name_jp": "ダンクマスター フラッシュ",
            "beer_name_core": "Dankmaster Flash",
            "search_hint": "Dankmaster Flash Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-dankmaster-flash/6390587",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573850",
        "name": "シングルヒル : イーストサイド IPA | Single Hill: Eastside IPA",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-eastside-ipa/2696024",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Eastside IPA",
            "beer_name_jp": "イーストサイド IPA",
            "beer_name_core": "Eastside IPA",
            "search_hint": "Eastside IPA Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-eastside-ipa/2696024",
        },
    },
    {
        "url": "https://beervolta.com/?pid=194573849",
        "name": "シングルヒル : フレッシュホップ ラテラル A (2026) | Single Hill: Fresh Hop Lateral A (2026)",
        "untappd_url": "https://untappd.com/b/single-hill-brewing-fresh-hop-lateral-a-2026/6961659",
        "gemini_update": {
            "brewery_name_en": "Single Hill Brewing",
            "brewery_name_jp": "シングルヒル",
            "beer_name_en": "Fresh Hop Lateral A (2026)",
            "beer_name_jp": "フレッシュホップ ラテラル A (2026)",
            "beer_name_core": "Fresh Hop Lateral A",
            "search_hint": "Fresh Hop Lateral A 2026 Single Hill Brewing",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/single-hill-brewing-fresh-hop-lateral-a-2026/6961659",
        },
    },
    # --- Untappd未紐付け在庫ビールから新規特定 (1件) ---
    {
        "url": "https://witchcraftmarket.com/products/sonar-tune",
        "name": "[AMAKUSA SONAR BEER] SONAR TUNE/ ソナーチューン",
        "untappd_url": "https://untappd.com/b/kumamoto-craft-beer-company-sonar-tune/7659113",
        "gemini_update": {
            "brewery_name_en": "Kumamoto Craft Beer Company",
            "brewery_name_jp": "天草ソナービール",
            "beer_name_en": "Sonar Tune",
            "beer_name_jp": "ソナーチューン",
            "beer_name_core": "Sonar Tune",
            "search_hint": "Sonar Tune Kumamoto Craft Beer Company",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kumamoto-craft-beer-company-sonar-tune/7659113",
        },
    },
]

# 4. Untappd未登録・バリアント特定不可確認済みアイテム (調査日時のみ更新)
UNLINKED_CHECKED_URLS = [
    "https://beer-chouseiya.shop/shopdetail/000000002921",  # 【八郷 秋あがり/大山Gビール】 (2025/2026年版未登録)
    "https://beervolta.com/?pid=173884556",                 # サイドプロジェクト / Side Project Single Farm (ホップバリアント未記載のため特定不可)
    "https://www.arome.jp/products/detail.php?product_id=8351",  # トラップドア / トラップトバーフェスト (Festbier) (Untappd未登録)
]

# 5. Untappd詳細取得・最新化対象 (是正・新規・ローリング監査・直近確認)
BEER_REFRESH_URLS = [
    # 是正・メタデータ補正対象
    "https://untappd.com/b/ikspiari-co-harvestmoon-pale-ale/98597",
    "https://untappd.com/b/minamishinshu-beer-ogna-india-pale-ale/5027734",
    # 新規エンリッチ対象 (14件)
    "https://untappd.com/b/uchu-brewing-break3-uchu-break3/7682783",
    "https://untappd.com/b/tambaji-brewery-sansho-no-ale/3500096",
    "https://untappd.com/b/tambaji-brewery-smoke-ale/2672132",
    "https://untappd.com/b/tambaji-brewery-tamba-ume-sour/6565386",
    "https://untappd.com/b/tambaji-brewery-tamba-chestnut-ale/2428023",
    "https://untappd.com/b/west-coast-brewing-hop-chef/7682882",
    "https://untappd.com/b/west-coast-brewing-marzen/7682881",
    "https://untappd.com/b/test-music-of-the-spheres/7609930",
    "https://untappd.com/b/test-tickets-to-the-sunset/6921498",
    "https://untappd.com/b/single-hill-brewing-five-sisters-2026/6961657",
    "https://untappd.com/b/single-hill-brewing-dankmaster-flash/6390587",
    "https://untappd.com/b/single-hill-brewing-eastside-ipa/2696024",
    "https://untappd.com/b/single-hill-brewing-fresh-hop-lateral-a-2026/6961659",
    "https://untappd.com/b/kumamoto-craft-beer-company-sonar-tune/7659113",
    # ローリング巡回監査 (5件)
    "https://untappd.com/b/tamamura-honten-co-shiga-kogen-pale-ale/55706",
    "https://untappd.com/b/minamishinshu-beer-co-yamaso-hop/2541105",
    "https://untappd.com/b/tamamura-honten-co-shiga-kogen-indian-summer-saison/57366",
    "https://untappd.com/b/tamamura-honten-co-shiga-kogen-porter/33626",
    "https://untappd.com/b/ikspiari-co-harvestmoon-pilsner/56440",
    # 直近確認対象 (残り3件も最新化)
    "https://untappd.com/b/minamishinshu-beer-cask-stout/4508078",
    "https://untappd.com/b/ikspiari-co-harvestmoon-brown-ale/132338",
    "https://untappd.com/b/ikspiari-co-harvestmoon-schwarz/60229",
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

    # 1. 非ビール商品の分類更新
    logger.info(f"\n[1] Marking {len(NON_BEER_ITEMS)} non-beer items...")
    for item in NON_BEER_ITEMS:
        url = item["url"]
        gem_update = dict(item["gemini_update"])
        logger.info(f"  Marking non-beer ({gem_update['product_type']}): {url}")

        gem_update["url"] = url
        gem_update["updated_at"] = now_iso
        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))

        run_db_op(lambda u=url: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": None,
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 2. 誤紐付け・メタデータ是正
    logger.info(f"\n[2] Correcting {len(FIX_MISASSIGNED_ITEMS)} misassigned/mismatched beer items...")
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

    # 3. 新規・未紐付け特定商品のエンリッチ登録
    logger.info(f"\n[3] Enriching {len(NEW_ENRICH_ITEMS)} items...")
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

    # 4. Untappd未登録・特定不可ビール調査済みマーク更新
    logger.info(f"\n[4] Updating investigation timestamp for {len(UNLINKED_CHECKED_URLS)} unlinked beers...")
    for url in UNLINKED_CHECKED_URLS:
        logger.info(f"  Checked (unlinked on Untappd): {url}")
        run_db_op(lambda u=url: sync_execute(sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso,
        }).eq("url", u)))

    # 5. Untappd データの詳細取得・最新化
    logger.info(f"\n[5] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} beers...")
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

    # 6. マテリアライズドビューのリフレッシュ
    logger.info("\n[6] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")


if __name__ == "__main__":
    asyncio.run(main())

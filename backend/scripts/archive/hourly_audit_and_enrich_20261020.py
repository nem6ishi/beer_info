import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 非ビール（グッズ等）の誤分類是正
NON_BEER_UPDATES = [
    {
        "url": "https://www.antenna-america.com/products/n136-c12001",
        "name": "Kure's Craft Beverage Kure's Ginger Beer (355ml) / キュリーズ ジンジャービア【8/27出荷】",
        "notes": "ノンアルコール クラフトソーダ/ミキサー (Non-alcoholic ginger beer mixer)"
    }
]

# 2. クラフト飲料・Untappd未登録確認済みアイテムのステータス更新
UNREGISTERED_BEERS = [
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001796",
        "notes": "若潮酒造コラボ芋焼酎ホップソーダ（クラフト飲料のためproduct_type='beer'として登録）"
    },
    {
        "url": "https://maruho.shop/products/hop-glow-soda-collab-w-若潮酒造-350ml-伊勢角麦酒",
        "notes": "若潮酒造コラボ芋焼酎ホップソーダ（クラフト飲料のためproduct_type='beer'として登録）"
    },
    {
        "url": "https://witchcraftmarket.com/products/maelstrom-hazy-ipa",
        "notes": "Untappd未登録確認済み (GAME BREW 魔海侯フォルネウス MAELSTROM HAZY IPA)"
    },
    {
        "url": "https://witchcraftmarket.com/products/trinity-blaster-pale-ale",
        "notes": "Untappd未登録確認済み (GAME BREW 魔龍公 ビューネイ TRINITY BLASTER PALE ALE)"
    },
    {
        "url": "https://witchcraftmarket.com/products/heat-wave-ipa",
        "notes": "Untappd未登録確認済み (GAME BREW 魔炎長 アウナス HEAT WAVE IPA)"
    },
    {
        "url": "https://witchcraftmarket.com/products/buchikamashi-helles",
        "notes": "Untappd未登録確認済み (GAME BREW 魔戦士公 アラケス BUCHIKAMASHI HELLES)"
    }
]

# 3. 監査で特定された実在ビールの新規Untappd紐付け・詳細エンリッチ
BEER_ENRICH_TARGETS = [
    {
        "url": "https://www.antenna-america.com/products/b062-c12020",
        "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-nz-pils/6287331",
        "gemini_update": {
            "brewery_name_en": "Crooked Stave Brewing Co.",
            "brewery_name_jp": "クルーキッドステイブ",
            "beer_name_en": "NZ Pils",
            "beer_name_core": "NZ Pils",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/crooked-stave-brewing-co-nz-pils/6287331"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c002-c12013",
        "untappd_url": "https://untappd.com/b/ace-cider-mango-cider/3865969",
        "gemini_update": {
            "brewery_name_en": "ACE Cider",
            "brewery_name_jp": "エースサイダー",
            "beer_name_en": "Mango Cider",
            "beer_name_core": "Mango Cider",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/ace-cider-mango-cider/3865969"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/c002-c12008",
        "untappd_url": "https://untappd.com/b/ace-cider-guava-cider/3351998",
        "gemini_update": {
            "brewery_name_en": "ACE Cider",
            "brewery_name_jp": "エースサイダー",
            "beer_name_en": "Guava Cider",
            "beer_name_core": "Guava Cider",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/ace-cider-guava-cider/3351998"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=5266",
        "untappd_url": "https://untappd.com/b/fiftyfifty-brewing-co-garrison-brothers-bourbon-barrel-eclipse-2024/6084309",
        "gemini_update": {
            "brewery_name_en": "FiftyFifty Brewing Co.",
            "brewery_name_jp": "フィフティフィフティ",
            "beer_name_en": "Garrison Brothers Bourbon Barrel Eclipse (2024)",
            "beer_name_core": "Garrison Brothers Bourbon Barrel Eclipse",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/fiftyfifty-brewing-co-garrison-brothers-bourbon-barrel-eclipse-2024/6084309"
        }
    },
    {
        "url": "https://beervolta.com/?pid=185148531",
        "untappd_url": "https://untappd.com/b/fiftyfifty-brewing-co-garrison-brothers-bourbon-barrel-eclipse-2024/6084309",
        "gemini_update": {
            "brewery_name_en": "FiftyFifty Brewing Co.",
            "brewery_name_jp": "フィフティフィフティ",
            "beer_name_en": "Garrison Brothers Bourbon Barrel Eclipse (2024)",
            "beer_name_core": "Garrison Brothers Bourbon Barrel Eclipse",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/fiftyfifty-brewing-co-garrison-brothers-bourbon-barrel-eclipse-2024/6084309"
        }
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Audit & Enrichment execution")
    logger.info("=" * 70)

    # 1. 非ビール誤判定の是正
    logger.info("\n[1] Updating non-beer / RTD items...")
    for item in NON_BEER_UPDATES:
        url = item["url"]
        up_res = sb.table("gemini_data").update({
            "product_type": "other",
            "updated_at": now_iso
        }).eq("url", url).execute()
        sb.table("untappd_search_failures").update({
            "resolved": True,
            "resolved_at": now_iso,
            "notes": f"Non-beer categorized as other: {item['notes']}"
        }).eq("product_url", url).execute()
        logger.info(f"  Fixed product_type -> other: {item['name']} (updated {len(up_res.data)} rows)")

    # 2. Untappd未登録ビールのステータス更新
    logger.info("\n[2] Updating status for unindexed beers in Untappd...")
    for item in UNREGISTERED_BEERS:
        url = item["url"]
        fail_res = sb.table("untappd_search_failures").update({
            "notes": item["notes"],
            "last_failed_at": now_iso
        }).eq("product_url", url).execute()
        logger.info(f"  Updated failure notes: {url} (updated {len(fail_res.data)} rows)")

    # 3. 実在ビールのUntappd連携・詳細取得
    logger.info(f"\n[3] Linking and enriching {len(BEER_ENRICH_TARGETS)} verified beers...")
    for item in BEER_ENRICH_TARGETS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"\n--- Processing: {url} -> {untappd_url} ---")

        # 3.1 gemini_data
        gem_res = sb.table("gemini_data").update(gem_update).eq("url", url).execute()
        logger.info(f"  [gemini_data] Updated: {len(gem_res.data)} rows")

        # 3.2 scraped_beers
        sb_res = sb.table("scraped_beers").update({
            "untappd_url": untappd_url,
            "untappd_enriched_at": now_iso
        }).eq("url", url).execute()
        logger.info(f"  [scraped_beers] Updated untappd_url: {len(sb_res.data)} rows")

        # 3.3 untappd_search_failures
        fail_res = sb.table("untappd_search_failures").update({
            "resolved": True,
            "resolved_at": now_iso,
            "notes": "Verified and resolved in hourly audit"
        }).eq("product_url", url).execute()
        if fail_res.data:
            logger.info(f"  [untappd_search_failures] Marked resolved: {len(fail_res.data)} rows")

        # 3.4 untappd_data (scrape & upsert if needed)
        existing = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute().data
        if not existing:
            logger.info(f"  [untappd_data] Scraping details for {untappd_url}...")
            details = await scrape_beer_details(untappd_url)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = untappd_url
                payload["fetched_at"] = now_iso
                upsert_res = sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                logger.info(f"  [untappd_data] Saved details for {details.get('untappd_beer_name')} (Rating: {details.get('rating')})")
            else:
                logger.warning(f"  [untappd_data] Failed to scrape details for {untappd_url}")
            await asyncio.sleep(2.0)
        else:
            logger.info(f"  [untappd_data] Already exists: {untappd_url}")

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

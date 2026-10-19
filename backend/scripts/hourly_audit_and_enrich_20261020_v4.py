import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. Untappd未登録確認済みアイテム（監査日時を更新して次回即時再検索を回避）
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://151l.shop/?pid=193571646",
        "name": "伊勢角屋麦酒 カドラボ041",
        "notes": "自社単離野生酵母テーブルセゾン Marginal Ⅵ。Untappd未登録を確認"
    },
    {
        "url": "https://witchcraftmarket.com/products/maelstrom-hazy-ipa",
        "name": "[GAME BREW] 魔海侯フォルネウス MAELSTROM HAZY IPA",
        "notes": "ロマンシング佐賀（スクエニ）コラボ限定醸造。Untappd未登録を確認"
    },
    {
        "url": "https://witchcraftmarket.com/products/buchikamashi-helles",
        "name": "[GAME BREW] 魔戦士公 アラケス BUCHIKAMASHI HELLES",
        "notes": "ロマンシング佐賀（スクエニ）コラボ限定醸造。Untappd未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "name": "伊勢角屋麦酒 カドラボ039",
        "notes": "ビアカクテル French 5³ meets beer。Untappd未登録を確認"
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8168",
        "name": "ビーイージーブルーイング リリコイ",
        "notes": "希少ホップNZ02限定IPA。Untappd未登録を確認"
    }
]

# 2. ローリング巡回・Untappdデータ最新化対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/fiftyfifty-brewing-co-eclipse-old-fashioned-blend-2024/6084313",
    "https://untappd.com/b/tired-hands-brewing-company-cherry-vanilla-psychedelic-lighthouse/6391788",
    "https://untappd.com/b/schneider-weisse-g-schneider-and-sohn-aventinus-eisbock-tap09/67996",
    "https://untappd.com/b/blade-factory-brewing-usuba/6607640",
    "https://untappd.com/b/oud-beersel-vandervelden-140-oude-geuze-vieille/4756684",
    "https://untappd.com/b/the-veil-brewing-co-old-sun-w-raspberries-and-blackberries/4082902",
    "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-rauchbier-weizen/472",
    "https://untappd.com/b/schlenkerla-heller-brau-trum-aecht-schlenkerla-erle-schwarzbier/5456891"
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Beer Audit & Enrichment Pipeline (v4)")
    logger.info("=" * 70)

    # 1. Untappd未登録アイテムの監査日時更新
    logger.info("\n[1] Updating audit timestamps for verified unregistered beers...")
    for item in AUDITED_UNREGISTERED_BEERS:
        p_url = item["url"]
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()

        sb.table("gemini_data").update({
            "updated_at": now_iso
        }).eq("url", p_url).execute()

        logger.info(f"  ✅ Audited: {item['name']}\n    -> {item['notes']}")

    # 2. Untappd データのスクレイピング・最新化
    logger.info(f"\n[2] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} beers...")
    success_count = 0
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            upsert_res = sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('rating')} | Checkins: {details.get('rating_count')}")
            success_count += 1
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(2.0)

    logger.info(f"\nSuccessfully updated {success_count}/{len(BEER_REFRESH_URLS)} Untappd beer records.")

    # 3. マテリアライズドビューのリフレッシュ
    logger.info("\n[3] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

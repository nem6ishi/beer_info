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
        "url": "https://beervolta.com/?pid=193912221",
        "name": "渥美半島醸造 : オパパ | Atsumi Peninsula: OPAPA",
        "notes": "渥美半島醸造のグレープフルーツIPA。ブルワリー登録はあるがOPAPAはUntappd未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=193938688",
        "name": "渥美半島醸造　オパパ（Atsumi Peninsula Brewing OPAPA）",
        "notes": "上記と同銘柄。Untappd未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "name": "【9/24（木）入荷予定】ファーメンタリー　お茶！大和（FARMENTRY OCHA! YAMATO）",
        "notes": "Farmentryによる月ヶ瀬大和茶使用ウィートエール。ブルワリー登録はあるがOCHA! YAMATOはUntappd未登録を確認"
    },
    {
        "url": "https://beervolta.com/?pid=193865151",
        "name": "バッテン : ゴールデン ピグ | Vatten: Golden Pig",
        "notes": "Vatten Brewingの3周年記念限定Session IPA。Untappd未登録を確認"
    },
    {
        "url": "https://beervolta.com/?pid=193866863",
        "name": "セッションズ : はっさくスマッシュ | Session's: Hassaku Smash",
        "notes": "Session's Breweryの八朔ピール使用ペールエール。Untappd未登録を確認"
    }
]

# 2. ローリング巡回・Untappdデータ最新化対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/paperback-brewing-co-breaking-balls/6698566",
    "https://untappd.com/b/boerenerf-gueuze-cuvee-heritage-2023-bottle/5784209",
    "https://untappd.com/b/namachan-brewing-nama/6901950",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-red-010/6961963",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yama-bushi-blonde-007/6961953"
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Beer Audit & Enrichment Pipeline (v5)")
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

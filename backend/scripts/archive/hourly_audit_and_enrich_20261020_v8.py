import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 未エンリッチ商品（今回は0件）
NEW_ENRICH_ITEMS = []

# 2. ローリング巡回・Untappdデータ最新化対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/smog-city-brewing-co-dynamic-pressure/3908351",
    "https://untappd.com/b/ajb-co-fruited-sour-cassis-barrel/6596028",
    "https://untappd.com/b/unsung-brewing-co-shatterspike/3394872",
    "https://untappd.com/b/isekado-kadolabo-040-miso/6847859"
]

# 3. Untappd未登録確認済みアイテム（監査日時を更新して次回即時再検索を回避）
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://beervolta.com/?pid=193865151",
        "name": "バッテン : ゴールデン ピグ | Vatten: Golden Pig (BEER VOLTA)",
        "notes": "Vatten Brewing（熊本県）の3周年醸造Session IPA。Untappdブルワリー銘柄一覧25種に未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "name": "【9/24（木）入荷予定】ファーメンタリー　お茶！大和（FARMENTRY OCHA! YAMATO） (一期一会～る)",
        "notes": "Farmentryの日本茶使用ビール。UntappdにはOCHA! -Longjing-のみ存在し、OCHA! YAMATOは未登録を確認"
    },
    {
        "url": "https://beervolta.com/?pid=193866863",
        "name": "セッションズ : はっさくスマッシュ | Session's: Hassaku Smash (BEER VOLTA)",
        "notes": "Session's Brewery（広島）の八朔ペールエール（ABV 5.5%）。Untappdブルワリー銘柄一覧25種に未登録を確認"
    },
    {
        "url": "https://witchcraftmarket.com/products/buchikamashi-helles",
        "name": "[GAME BREW] 魔戦士公 アラケス BUCHIKAMASHI HELLES / ブチカマシ ヘレス (WITCH CRAFT MARKET)",
        "notes": "GAME BREW（佐賀）とロマンシング佐賀（サガシリーズ・四魔貴族）コラボヘレス。Untappdブルワリー銘柄一覧25種に未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "name": "伊勢角屋麦酒　カドラボ039（ISEKADOYA BEER KADOLABO 039） (一期一会～る)",
        "notes": "ISEKADOの実験シリーズ「KADOLABO 039 French 5³ meets beer」。Untappd未登録を確認"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Beer Audit & Enrichment Pipeline (v8)")
    logger.info("=" * 70)

    # 1. 未エンリッチ商品のDB登録 & Untappdスクレイピング（今回は0件）
    if NEW_ENRICH_ITEMS:
        logger.info("\n[1] Enriching previously unenriched beers...")
        for item in NEW_ENRICH_ITEMS:
            url = item["url"]
            untappd_url = item["untappd_url"]
            gem_update = item["gemini_update"]

            logger.info(f"  Enriching {url} -> {untappd_url}")

            # gemini_data upsert
            gem_update["url"] = url
            gem_update["updated_at"] = now_iso
            sb.table("gemini_data").upsert(gem_update, on_conflict="url").execute()

            # scraped_beers update
            sb.table("scraped_beers").update({
                "untappd_url": untappd_url,
                "untappd_enriched_at": now_iso
            }).eq("url", url).execute()

            # untappd_data scrape & upsert
            details = await scrape_beer_details(untappd_url)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = untappd_url
                payload["fetched_at"] = now_iso
                sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                logger.info(f"  ✅ Enriched & Saved Untappd Data: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('rating')})")
            else:
                logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
            await asyncio.sleep(2.0)
    else:
        logger.info("\n[1] No unenriched beers to process.")

    # 2. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[2] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('rating')} | Checkins: {details.get('rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(2.0)

    # 3. Untappd未登録アイテムの監査日時更新
    logger.info(f"\n[3] Updating audit timestamps for {len(AUDITED_UNREGISTERED_BEERS)} verified unregistered beers...")
    for item in AUDITED_UNREGISTERED_BEERS:
        p_url = item["url"]
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()

        sb.table("gemini_data").update({
            "updated_at": now_iso
        }).eq("url", p_url).execute()

        logger.info(f"  ✅ Audited: {item['name']}\n    -> {item['notes']}")

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

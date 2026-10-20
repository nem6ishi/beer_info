import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 未エンリッチ商品（特定済みUntappd URL）
NEW_ENRICH_ITEMS = [
    {
        "url": "https://witchcraftmarket.com/products/everything-passes",
        "untappd_url": "https://untappd.com/b/finback-brewery-everything-passes/6783024",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Everything Passes",
            "beer_name_jp": "エブリシング パセズ",
            "beer_name_core": "Everything Passes",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-everything-passes/6783024"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/beyond",
        "untappd_url": "https://untappd.com/b/finback-brewery-beyond/6733686",
        "gemini_update": {
            "brewery_name_en": "Finback Brewery",
            "brewery_name_jp": "フィンバック",
            "beer_name_en": "Beyond",
            "beer_name_jp": "ビヨンド",
            "beer_name_core": "Beyond",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/finback-brewery-beyond/6733686"
        }
    },
    {
        "url": "https://witchcraftmarket.com/products/patagonia-provision-organic-lager",
        "untappd_url": "https://untappd.com/b/deschutes-brewery-patagonia-provisions-organic-lager/6540361",
        "gemini_update": {
            "brewery_name_en": "Deschutes Brewery",
            "brewery_name_jp": "デシューツ",
            "beer_name_en": "Patagonia Provisions Organic Lager",
            "beer_name_jp": "パタゴニア プロビジョンズ オーガニックラガー",
            "beer_name_core": "Patagonia Provisions Organic Lager",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/deschutes-brewery-patagonia-provisions-organic-lager/6540361"
        }
    }
]

# 2. ローリング巡回・Untappdデータ最新化対象（ユニーク5銘柄）
BEER_REFRESH_URLS = [
    "https://untappd.com/b/los-angeles-ale-works-steady-coasting/5871472",
    "https://untappd.com/b/los-angeles-ale-works-dead-cowboy/2713923",
    "https://untappd.com/b/almanac-fruit-punch-sournova/5210630",
    "https://untappd.com/b/pure-project-brewing-diamond-dust/2042188",
    "https://untappd.com/b/pure-project-brewing-tropical-mist/2863981"
]

# 3. Untappd未登録確認済みアイテム（監査日時を更新して次回即時再検索を回避）
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://beervolta.com/?pid=193865151",
        "name": "バッテン : ゴールデン ピグ | Vatten: Golden Pig (BEER VOLTA)",
        "notes": "Vatten Brewing（熊本）のPigシリーズ新作。Space Pig等は登録あるがGolden Pigは未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "name": "伊勢角屋麦酒　カドラボ039（ISEKADOYA BEER KADOLABO 039） (一期一会～る)",
        "notes": "伊勢角屋麦酒の実験醸造カドラボシリーズ。Untappdには029まで登録、039は未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "name": "【9/24（木）入荷予定】ファーメンタリー　お茶！大和（FARMENTRY OCHA! YAMATO） (一期一会～る)",
        "notes": "Farmentry（山梨）の新興醸造所。Untappdブルワリーページ登録ビール0件で未登録を確認"
    },
    {
        "url": "https://151l.shop/?pid=193938688",
        "name": "渥美半島醸造　オパパ（Atsumi Peninsula Brewing OPAPA） (一期一会～る)",
        "notes": "渥美半島醸造（愛知）のGrapefruit IPA。Untappdブルワリー全登録銘柄に未登録を確認"
    },
    {
        "url": "https://witchcraftmarket.com/products/trinity-blaster-pale-ale",
        "name": "[GAME BREW] 魔龍公 ビューネイ TRINITY BLASTER PALE ALE (WITCH CRAFT MARKET)",
        "notes": "GAME BREW（佐賀）とロマンシング佐賀（サガシリーズ・四魔貴族）コラボ。Untappd未登録を確認"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Beer Audit & Enrichment Pipeline (v11)")
    logger.info("=" * 70)

    # 1. 未エンリッチ商品のDB登録 & Untappdスクレイピング
    if NEW_ENRICH_ITEMS:
        logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} unenriched beers...")
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
                logger.info(f"  ✅ Enriched & Saved Untappd Data: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
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
            logger.info(f"  ✅ Updated: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} | Rating: {details.get('untappd_rating')} | Checkins: {details.get('untappd_rating_count')}")
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

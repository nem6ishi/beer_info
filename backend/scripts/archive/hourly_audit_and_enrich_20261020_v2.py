import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 非ビール（RTD / カクテル）の誤判定・誤紐付け是正
NON_BEER_UPDATES = [
    {
        "url": "https://www.antenna-america.com/products/r136-c12003",
        "name": "Kure's Craft Beverage Strawberry Vodka Lemonade (355ml) / ストロベリー ウォッカ レモネード【8/27出荷】",
        "notes": "RTD / Vodka Lemonade (解除: Früli Strawberry Beer 誤紐付け)"
    },
    {
        "url": "https://www.antenna-america.com/products/r136-c12004",
        "name": "Kure's Craft Beverage Dirty Shirley (355ml) / ダーティー シャーリー【8/27出荷】",
        "notes": "RTD / Vodka Shirley cocktail"
    },
    {
        "url": "https://www.antenna-america.com/products/r136-c12001",
        "name": "Kure's Craft Beverage Colorado Mule (355ml) / コロラド ミュール【8/27出荷】",
        "notes": "RTD / Moscow Mule cocktail"
    },
    {
        "url": "https://www.antenna-america.com/products/r136-c12002",
        "name": "Kure's Craft Beverage Orange Cream Vodka Pop (355ml) / オレンジクリーム ウォッカポップ【8/27出荷】",
        "notes": "RTD / Vodka Pop cocktail"
    }
]

# 2. Untappd未登録ビールのステータス更新（小ロット・限定醸造等）
UNREGISTERED_BEERS = [
    {
        "url": "https://witchcraftmarket.com/products/maelstrom-hazy-ipa",
        "notes": "Untappd未登録確認済み (GAME BREW 魔海侯フォルネウス MAELSTROM HAZY IPA)"
    },
    {
        "url": "https://witchcraftmarket.com/products/buchikamashi-helles",
        "notes": "Untappd未登録確認済み (GAME BREW 魔戦士公 アラケス BUCHIKAMASHI HELLES)"
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8167",
        "notes": "Untappd未登録確認済み (Be Easy Brewing / どさ？ゆっこさ！ Dosa? Yukkosa!)"
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8168",
        "notes": "Untappd未登録確認済み (Be Easy Brewing / リリコイ Lilikoi)"
    },
    {
        "url": "https://beervolta.com/?pid=193912221",
        "notes": "Untappd未登録確認済み (渥美半島醸造 / オパパ OPAPA)"
    },
    {
        "url": "https://151l.shop/?pid=193938688",
        "notes": "Untappd未登録確認済み (渥美半島醸造 / オパパ OPAPA)"
    },
    {
        "url": "https://beervolta.com/?pid=193866863",
        "notes": "Untappd未登録確認済み (Session's Brewery / はっさくスマッシュ Hassaku Smash)"
    },
    {
        "url": "https://beervolta.com/?pid=193865151",
        "notes": "Untappd未登録確認済み (Vatten Brewing / ゴールデン ピグ Golden Pig)"
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "notes": "Untappd未登録確認済み (FARMENTRY / お茶！大和 OCHA! YAMATO)"
    },
    {
        "url": "https://151l.shop/?pid=192919839",
        "notes": "Untappd未登録確認済み (伊勢角屋麦酒 / カドラボ039 KADOLABO 039)"
    },
    {
        "url": "https://151l.shop/?pid=193571646",
        "notes": "Untappd未登録確認済み (伊勢角屋麦酒 / カドラボ041 KADOLABO 041)"
    }
]

# 3. 最古 Untappd 取得データのローリング再取得・最新化
BEER_REFRESH_URLS = [
    "https://untappd.com/b/kemker-kultuur-brauerei-j-kemker-lust-2021-cassis/4962668",
    "https://untappd.com/b/himitsu-beer-doron/6595939",
    "https://untappd.com/b/tamamura-honten-co-barrel-aged-yamabushi-osmk-ore-no-sake-wo-mazeruno-ka/6500140",
    "https://untappd.com/b/great-dane-brewing-sendai-sagae-cherry-tripel/6083247",
    "https://untappd.com/b/track-brewing-company-ethos/6736994"
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("🚀 Starting Hourly Audit & Enrichment Pipeline (v2)")
    logger.info("=" * 70)

    # 1. 非ビール（RTD）の誤判定・誤紐付け是正
    logger.info("\n[1] Updating non-beer / RTD items...")
    for item in NON_BEER_UPDATES:
        url = item["url"]
        up_res = sb.table("gemini_data").update({
            "product_type": "other",
            "untappd_url": None,
            "updated_at": now_iso
        }).eq("url", url).execute()

        sb_res = sb.table("scraped_beers").update({
            "untappd_url": None,
            "untappd_enriched_at": now_iso
        }).eq("url", url).execute()

        sb.table("untappd_search_failures").update({
            "resolved": True,
            "resolved_at": now_iso,
            "notes": item["notes"]
        }).eq("product_url", url).execute()

        logger.info(f"  Fixed product_type -> other: {item['name']} (gemini: {len(up_res.data)}, scraped: {len(sb_res.data)})")

    # 2. Untappd未登録ビールのステータス更新
    logger.info("\n[2] Updating status for unindexed beers in Untappd...")
    for item in UNREGISTERED_BEERS:
        url = item["url"]
        # scraped_beers の untappd_enriched_at を更新して未エンリッチ滞留を防ぐ
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", url).execute()

        # untappd_search_failures のステータスを最新化
        fail_res = sb.table("untappd_search_failures").update({
            "notes": item["notes"],
            "last_failed_at": now_iso
        }).eq("product_url", url).execute()
        if not fail_res.data:
            # 存在しない場合は新規追加
            sb.table("untappd_search_failures").insert({
                "product_url": url,
                "notes": item["notes"],
                "last_failed_at": now_iso,
                "first_failed_at": now_iso,
                "search_attempts": 1,
                "failure_reason": "no_results"
            }).execute()
        logger.info(f"  Marked unindexed: {url}")

    # 3. 最古 Untappd データのローリング再取得・最新化
    logger.info(f"\n[3] Rolling refresh for {len(BEER_REFRESH_URLS)} oldest Untappd beers...")
    for untappd_url in BEER_REFRESH_URLS:
        logger.info(f"  Scraping latest details for {untappd_url}...")
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            upsert_res = sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Updated: {details.get('untappd_beer_name')} | Rating: {details.get('rating')} | Checkins: {details.get('rating_count')}")
        else:
            logger.warning(f"  ❌ Failed to scrape details for {untappd_url}")
        await asyncio.sleep(2.0)

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

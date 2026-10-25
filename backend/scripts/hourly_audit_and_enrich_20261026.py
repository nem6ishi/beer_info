import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未紐付けから調査特定できたもの）
NEW_ENRICH_ITEMS = [
    {
        "url": "https://maruho.shop/products/equis-350ml-passific",
        "untappd_url": "https://untappd.com/b/passific-brewing-equis/5578100",
        "gemini_update": {
            "brewery_name_en": "Passific Brewing",
            "brewery_name_jp": "パシフィックブルーイング",
            "beer_name_en": "Equis",
            "beer_name_jp": "エキスポ",
            "beer_name_core": "Equis",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/passific-brewing-equis/5578100"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8209",
        "untappd_url": "https://untappd.com/b/amaku-uku-aoito-2026/7628430",
        "gemini_update": {
            "brewery_name_en": "amaku uku",
            "brewery_name_jp": "甘く浮く",
            "beer_name_en": "aoito 2026",
            "beer_name_jp": "アオイト 2026",
            "beer_name_core": "aoito 2026",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/amaku-uku-aoito-2026/7628430"
        }
    }
]

# 2. ローリング巡回・Untappd データの最新化対象
BEER_REFRESH_URLS = [
    "https://untappd.com/b/tamamura-honten-co-shiga-kogen-fresh-hop-africa-pale-ale-2026/6918508",
    "https://untappd.com/b/gogoshima-beer-farm-azahar-de-iyokan/6844584",
    "https://untappd.com/b/revision-brewing-company-planet-lovetron/2419643",
    "https://untappd.com/b/modern-times-beer-parlay-easy/6619792"
]

# 3. 調査済みUntappd未登録ビール（監査日時を更新してローリング対象から次回以降へ送る）
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8167",
        "name": "ビーイージーブルーイング / どさ？ゆっこさ！ (West Coast IPA) 350ml缶 [Be Easy Brewing / Dosa？Yukkosa！]",
        "notes": "Untappd未登録（新作West Coast IPA）。DOSA YUSA等の過去銘柄とは別レシピ。"
    },
    {
        "url": "https://151l.shop/?pid=193571646",
        "name": "【9/19（土）入荷予定】伊勢角屋麦酒　カドラボ041（ISEKADOYA BEER KADOLABO 041）",
        "notes": "Untappd未登録（Kadolabo 041 Marginal Ⅵ / Table Saison 2.0%）。Untappd未登録。"
    },
    {
        "url": "https://151l.shop/?pid=194079981",
        "name": "【10/23-24入荷予定】バテレ　コティヌス（VERTERE Cotinus）",
        "notes": "Untappd未登録（新作Irish Red Ale）。Untappd未登録。"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. 新規エンリッチ
    logger.info(f"\n[1] Enriching {len(NEW_ENRICH_ITEMS)} target beers...")
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
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(0.5)

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
        await asyncio.sleep(0.5)

    # 3. Untappd未登録アイテムの監査日時更新
    logger.info(f"\n[3] Updating audit timestamps for {len(AUDITED_UNREGISTERED_BEERS)} verified unregistered beers...")
    for item in AUDITED_UNREGISTERED_BEERS:
        p_url = item["url"]
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", p_url).execute()

        sb.table("gemini_data").update({
            "product_type": "beer",
            "updated_at": now_iso
        }).eq("url", p_url).execute()

        logger.info(f"  ✅ Audited: {item['name']}\n    -> {item['notes']}")

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

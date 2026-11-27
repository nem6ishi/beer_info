import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品: 3件 + 未紐付けから特定した1件 = 計4件
NEW_ENRICH_ITEMS = [
    # --- 一期一会～る (RIKRI BREWING) ---
    {
        "url": "https://151l.shop/?pid=194120240",
        "untappd_url": "https://untappd.com/b/rikri-brewing-flypaper/7019033",
        "gemini_update": {
            "brewery_name_en": "RIKRI BREWING",
            "brewery_name_jp": "リクリブルーイング",
            "beer_name_en": "FlyPaper",
            "beer_name_jp": "フライペーパー",
            "beer_name_core": "FlyPaper",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rikri-brewing-flypaper/7019033"
        }
    },
    {
        "url": "https://151l.shop/?pid=194120177",
        "untappd_url": "https://untappd.com/b/rikri-brewing-big-hoppa/6609159",
        "gemini_update": {
            "brewery_name_en": "RIKRI BREWING",
            "brewery_name_jp": "リクリブルーイング",
            "beer_name_en": "Big Hoppa",
            "beer_name_jp": "ビッグホッパ",
            "beer_name_core": "Big Hoppa",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/rikri-brewing-big-hoppa/6609159"
        }
    },

    # --- マルホ酒店 (New Belgium Brewing Company) ---
    {
        "url": "https://maruho.shop/products/felix-aged-in-apple-whiskey-barrels-750ml-new-belgium",
        "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-felix-aged-in-apple-whiskey-barrels/2275095",
        "gemini_update": {
            "brewery_name_en": "New Belgium Brewing Company",
            "brewery_name_jp": "ニューベルジャン",
            "beer_name_en": "Felix Aged In Apple Whiskey Barrels",
            "beer_name_jp": "フェリックス エイジド イン アップル ウイスキー バレルズ",
            "beer_name_core": "Felix Aged In Apple Whiskey Barrels",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/new-belgium-brewing-company-felix-aged-in-apple-whiskey-barrels/2275095"
        }
    },

    # --- WITCH CRAFT MARKET (Barebottle Brewing Company) ---
    {
        "url": "https://witchcraftmarket.com/products/secret-truth-of-the-universe",
        "untappd_url": "https://untappd.com/b/barebottle-brewing-company-the-secret-truth-of-the-universe/2495559",
        "gemini_update": {
            "brewery_name_en": "Barebottle Brewing Company",
            "brewery_name_jp": "ベアボトル",
            "beer_name_en": "The Secret Truth of the Universe",
            "beer_name_jp": "ザ シークレット トゥルース オブ ザ ユニバース",
            "beer_name_core": "Secret Truth of the Universe",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/barebottle-brewing-company-the-secret-truth-of-the-universe/2495559"
        }
    }
]

# 2. ローリング巡回・情報更新対象 Untappd URL (4件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/west-coast-brewing-starwatcher-cbd/4194889",
    "https://untappd.com/b/trap-door-brewing-glowed-up/1889866",
    "https://untappd.com/b/garage-beer-co-knudsen/6630293",
    "https://untappd.com/b/varietal-beer-co-twine-climber/2593312",
]

# 3. 調査済みUntappd未登録ビール (監査タイムスタンプ更新対象: 4件)
AUDITED_UNREGISTERED_BEERS = [
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8167",
        "name": "ビーイージーブルーイング / どさ？ゆっこさ！ (West Coast IPA) 350ml缶 [Be Easy Brewing / Dosa？Yukkosa！]",
        "notes": "Be Easy Brewing の West Coast IPA。Untappd未登録を確認。"
    },
    {
        "url": "https://beervolta.com/?pid=193866863",
        "name": "セッションズ : はっさくスマッシュ | Session's: Hassaku Smash",
        "notes": "Session's Brewery 八朔使用 American Pale Ale。Untappd未登録を確認。"
    },
    {
        "url": "https://151l.shop/?pid=193571646",
        "name": "伊勢角屋麦酒　カドラボ041（ISEKADOYA BEER KADOLABO 041 Marginal Ⅵ）",
        "notes": "伊勢角屋麦酒 Marginal VI ローアルコール・テーブルセゾン。Untappd未登録を確認。"
    },
    {
        "url": "https://151l.shop/?pid=194079981",
        "name": "バテレ　コティヌス（VERTERE Cotinus）",
        "notes": "VERTERE の新作 Irish Red Ale。Untappd未登録を確認（GlassHouseの別ビールとの誤認防止）。"
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 誤って挿入された6157833のクリーンアップ
    sb.table("untappd_data").delete().eq("untappd_url", "https://untappd.com/b/rikri-brewing-big-hoppa/6157833").execute()
    sb.table("untappd_data").delete().eq("untappd_url", "https://untappd.com/b/heavy-rotation-brewing-company-black-cherry/6157833").execute()

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
        existing_u = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute()
        if existing_u.data:
            logger.info(f"  ⚡ Already in untappd_data, updating details: {untappd_url}")
        
        details = await scrape_beer_details(untappd_url)
        if details:
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
            logger.info(f"  ✅ Enriched & Saved: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')} (Rating: {details.get('untappd_rating')})")
        else:
            logger.warning(f"  ⚠️ Could not scrape Untappd details for {untappd_url}")
        await asyncio.sleep(1.0)

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
        await asyncio.sleep(1.0)

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

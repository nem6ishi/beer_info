import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付け特定2件 + 誤紐付け修正1件 = 計23件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8247",
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
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8249",
        "untappd_url": "https://untappd.com/b/nobody-brewing-the-japanoise/7628507",
        "gemini_update": {
            "brewery_name_en": "Nobody Brewing",
            "brewery_name_jp": "ノーバディーブルーイング",
            "beer_name_en": "The Japanoise",
            "beer_name_jp": "ザ ジャパノイズ",
            "beer_name_core": "The Japanoise",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/nobody-brewing-the-japanoise/7628507"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8248",
        "untappd_url": "https://untappd.com/b/nobody-brewing-five-seasons/7631340",
        "gemini_update": {
            "brewery_name_en": "Nobody Brewing",
            "brewery_name_jp": "ノーバディーブルーイング",
            "beer_name_en": "Five Seasons",
            "beer_name_jp": "ファイブ シーズンズ",
            "beer_name_core": "Five Seasons",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/nobody-brewing-five-seasons/7631340"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8245",
        "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-dry-hop-series-galaxy-and-saaz-2023/5839781",
        "gemini_update": {
            "brewery_name_en": "Blind Enthusiasm Brewing",
            "brewery_name_jp": "ブラインドエンスージアズム",
            "beer_name_en": "Dry Hop Series: Galaxy & Saaz 2023",
            "beer_name_jp": "ドライホップシリーズ：ギャラクシー＆ザーツ 2023",
            "beer_name_core": "Galaxy & Saaz 2023",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/blind-enthusiasm-brewing-dry-hop-series-galaxy-and-saaz-2023/5839781"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060765",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Tahoe Deep",
            "beer_name_jp": "タホディープ",
            "beer_name_core": "Tahoe Deep",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060876",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-simtra-triple-ipa/93848",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Simtra TIPA",
            "beer_name_jp": "シムトラ TIPA",
            "beer_name_core": "Simtra",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-simtra-triple-ipa/93848"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060919",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-slooow-mo-ipa/2461375",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Slooow Mo",
            "beer_name_jp": "スローモー",
            "beer_name_core": "Slooow Mo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-slooow-mo-ipa/2461375"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188532",
        "untappd_url": "https://untappd.com/b/hudson-valley-brewery-soleil-sipa/2597723",
        "gemini_update": {
            "brewery_name_en": "Hudson Valley Brewery",
            "brewery_name_jp": "ハドソンバレー",
            "beer_name_en": "Soleil",
            "beer_name_jp": "ソレイユ",
            "beer_name_core": "Soleil",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hudson-valley-brewery-soleil-sipa/2597723"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188633",
        "untappd_url": "https://untappd.com/b/hudson-valley-brewery-planetfall/2202576",
        "gemini_update": {
            "brewery_name_en": "Hudson Valley Brewery",
            "brewery_name_jp": "ハドソンバレー",
            "beer_name_en": "Planetfall",
            "beer_name_jp": "プラネットフォール",
            "beer_name_core": "Planetfall",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hudson-valley-brewery-planetfall/2202576"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188340",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-power-tools/1770879",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Power Tools",
            "beer_name_jp": "パワーツールズ",
            "beer_name_core": "Power Tools",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-power-tools/1770879"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188350",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-wrench-neipa/2234085",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Wrench",
            "beer_name_jp": "レンチ",
            "beer_name_core": "Wrench",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-wrench-neipa/2234085"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188356",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-torque-wrench/2441461",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Torque Wrench",
            "beer_name_jp": "トルクレンチ",
            "beer_name_core": "Torque Wrench",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-torque-wrench/2441461"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188369",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-impact-wrench/3574079",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Impact Wrench",
            "beer_name_jp": "インパクトレンチ",
            "beer_name_core": "Impact Wrench",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-impact-wrench/3574079"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188424",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-week-521-space-wrench/6765460",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Week 521 Space Wrench",
            "beer_name_jp": "ウィーク521 スペースレンチ",
            "beer_name_core": "Week 521 Space Wrench",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-week-521-space-wrench/6765460"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188432",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-hex-bolt/6105290",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Hex Bolt",
            "beer_name_jp": "ヘックスボルト",
            "beer_name_core": "Hex Bolt",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-hex-bolt/6105290"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188520",
        "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-zed-lupulin/2253802",
        "gemini_update": {
            "brewery_name_en": "Kings County Brewers Collective",
            "brewery_name_jp": "キングスカウンティ ブルワーズ コレクティブ",
            "beer_name_en": "Zed Lupulin",
            "beer_name_jp": "ゼッドルプリン",
            "beer_name_core": "Zed Lupulin",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-zed-lupulin/2253802"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188661",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-coal-miners-daughter/6760194",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Coal Miner's Daughter",
            "beer_name_jp": "コールマイナーズドーター",
            "beer_name_core": "Coal Miner's Daughter",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-coal-miners-daughter/6760194"
        }
    },
    {
        "url": "https://151l.shop/?pid=194188707",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-zero-coast/4431073",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Zero Coast",
            "beer_name_jp": "ゼロコースト",
            "beer_name_core": "Zero Coast",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-zero-coast/4431073"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194186424",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-slooow-mo-ipa/2461375",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Slooow Mo",
            "beer_name_jp": "スローモ",
            "beer_name_core": "Slooow Mo",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-slooow-mo-ipa/2461375"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194186422",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-hoptologist/81914",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Hoptologist",
            "beer_name_jp": "ホプトロジスト",
            "beer_name_core": "Hoptologist",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-hoptologist/81914"
        }
    },
    # --- 誤紐付け是正 (Tonewood Halcyon -> 久福 072福 岡山清水白桃Weizen) ---
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003196",
        "untappd_url": "https://untappd.com/b/kyufuku-brewing-honjima-072-weizen2026/6880002",
        "gemini_update": {
            "brewery_name_en": "Kyufuku Brewing Honjima",
            "brewery_name_jp": "久福ブルーイング福生",
            "beer_name_en": "072福 岡山清水白桃Weizen",
            "beer_name_jp": "072福 岡山清水白桃ヴァイツェン",
            "beer_name_core": "072福 岡山清水白桃Weizen",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kyufuku-brewing-honjima-072-weizen2026/6880002"
        }
    },
    # --- Untappd未紐付け在庫から特定できたアイテム ---
    {
        "url": "https://www.antenna-america.com/products/b128-c16014",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-football-is-better-with-cheese-and-sausage/6552719",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド",
            "beer_name_en": "Football Is Better With Sausage and Cheese",
            "beer_name_jp": "フットボール イズ ベター ウィズ ソーセージ アンド チーズ",
            "beer_name_core": "Football Is Better With Sausage and Cheese",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-football-is-better-with-cheese-and-sausage/6552719"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12003",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-door-county-cherry-wheat/45979",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド",
            "beer_name_en": "Door County Cherry Wheat",
            "beer_name_jp": "チェリー ウィート",
            "beer_name_core": "Door County Cherry Wheat",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-door-county-cherry-wheat/45979"
        }
    }
]

# 2. 未登録確認済み・調査タイムスタンプ更新対象 (Untappd未登録のビール)
UNREGISTERED_INSPECTED_URLS = [
    "https://151l.shop/?pid=194079981",                          # VERTERE / Cotinus
    "https://151l.shop/?pid=193571646",                          # ISEKADOYA / KADOLABO 041
    "https://www.arome.jp/products/detail.php?product_id=8167",   # Be Easy Brewing / Dosa? Yukkosa!
]

# 3. ローリング巡回・Untappd データの最新化対象 (4件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/isekado/7176491",
    "https://untappd.com/b/ise-kadoya-brain-melting-ultra-heaven-3-x-ipa/6653697",
    "https://untappd.com/b/isekado-ipa/6927586",
    "https://untappd.com/b/namachan-brewing-himarayan-pepper-ale/6494668"
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. 新規エンリッチ & 修正
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

    # 2. 未登録確認済みアイテムの調査タイムスタンプ更新
    logger.info(f"\n[2] Updating inspected timestamp for {len(UNREGISTERED_INSPECTED_URLS)} untappd-unregistered beers...")
    for url in UNREGISTERED_INSPECTED_URLS:
        sb.table("scraped_beers").update({
            "untappd_enriched_at": now_iso
        }).eq("url", url).execute()
        logger.info(f"  ✅ Timestamp updated for: {url}")

    # 3. ローリング巡回・Untappd データの最新化
    logger.info(f"\n[3] Scraping & updating Untappd details for {len(BEER_REFRESH_URLS)} rolling audit beers...")
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

    # 4. マテリアライズドビューのリフレッシュ
    logger.info("\n[4] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

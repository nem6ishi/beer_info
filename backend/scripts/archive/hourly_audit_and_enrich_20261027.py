import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付け特定5件 = 計25件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先) ---
    {
        "url": "https://www.antenna-america.com/products/b039-c16006",
        "untappd_url": "https://untappd.com/b/49th-state-brewing-spruceplosion/3770909",
        "gemini_update": {
            "brewery_name_en": "49th State Brewing",
            "brewery_name_jp": "フォーティナインス ステート ブルーイング",
            "beer_name_en": "Spruceplosion",
            "beer_name_jp": "スプルースプロージョン",
            "beer_name_core": "Spruceplosion",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/49th-state-brewing-spruceplosion/3770909"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194169026",
        "untappd_url": "https://untappd.com/b/y-market-brewing-ichiban-bakujyu-ipa/7637879",
        "gemini_update": {
            "brewery_name_en": "Y.Market Brewing",
            "brewery_name_jp": "ワイマーケットブルーイング",
            "beer_name_en": "Ichiban Bakujyu (一番麦汁) IPA",
            "beer_name_jp": "一番麦汁IPA",
            "beer_name_core": "Ichiban Bakujyu IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/y-market-brewing-ichiban-bakujyu-ipa/7637879"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b114-c16017",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-shogun-japanese-rice-lager/7616594",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Company",
            "brewery_name_jp": "エンボルデン ビア カンパニー",
            "beer_name_en": "Shogun Japanese Rice Lager",
            "beer_name_jp": "ショーグン ジャパニーズ ライスラガー",
            "beer_name_core": "Shogun Japanese Rice Lager",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-shogun-japanese-rice-lager/7616594"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b114-c16018",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-room-service/6829128",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Company",
            "brewery_name_jp": "エンボルデン ビア カンパニー",
            "beer_name_en": "Room Service",
            "beer_name_jp": "ルームサービス",
            "beer_name_core": "Room Service",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-room-service/6829128"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12015",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-saving-gracie-juicy-ipa/6614669",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド ブルワリー",
            "beer_name_en": "Saving Gracie Juicy IPA",
            "beer_name_jp": "セービング グレイシー ジューシーIPA",
            "beer_name_core": "Saving Gracie Juicy IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-saving-gracie-juicy-ipa/6614669"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12017",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-saving-gracie-sour-berry-ale/6295879",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド ブルワリー",
            "beer_name_en": "Saving Gracie Sour Berry Ale",
            "beer_name_jp": "セービング グレイシー サワー ベリーエール",
            "beer_name_core": "Saving Gracie Sour Berry Ale",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-saving-gracie-sour-berry-ale/6295879"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b129-c12001",
        "untappd_url": "https://untappd.com/b/mother-road-brewing-company-tower-station-ipa/1184504",
        "gemini_update": {
            "brewery_name_en": "Mother Road Brewing Company",
            "brewery_name_jp": "マザーロード ブルーイング",
            "beer_name_en": "Tower Station IPA",
            "beer_name_jp": "タワーステーション IPA",
            "beer_name_core": "Tower Station IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mother-road-brewing-company-tower-station-ipa/1184504"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b129-c12002",
        "untappd_url": "https://untappd.com/b/mother-road-brewing-company-turbo-tower-station/5449549",
        "gemini_update": {
            "brewery_name_en": "Mother Road Brewing Company",
            "brewery_name_jp": "マザーロード ブルーイング",
            "beer_name_en": "Turbo Tower Station",
            "beer_name_jp": "ターボ タワーステーション",
            "beer_name_core": "Turbo Tower Station",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mother-road-brewing-company-turbo-tower-station/5449549"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b129-c12003",
        "untappd_url": "https://untappd.com/b/mother-road-brewing-company-tower-station-roadside-grove/5046844",
        "gemini_update": {
            "brewery_name_en": "Mother Road Brewing Company",
            "brewery_name_jp": "マザーロード ブルーイング",
            "beer_name_en": "Tower Station - Roadside Grove",
            "beer_name_jp": "タワーステーション ロードサイド グローブ",
            "beer_name_core": "Tower Station Roadside Grove",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mother-road-brewing-company-tower-station-roadside-grove/5046844"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b129-c16004",
        "untappd_url": "https://untappd.com/b/mother-road-brewing-company-limited-visibility/3068661",
        "gemini_update": {
            "brewery_name_en": "Mother Road Brewing Company",
            "brewery_name_jp": "マザーロード ブルーイング",
            "beer_name_en": "Limited Visibility",
            "beer_name_jp": "リミテッド ヴィジビリティー",
            "beer_name_core": "Limited Visibility",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mother-road-brewing-company-limited-visibility/3068661"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12001",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-hinterland-ipa/66598",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド ブルワリー",
            "beer_name_en": "Hinterland IPA",
            "beer_name_jp": "ヒンターランド IPA",
            "beer_name_core": "Hinterland IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-hinterland-ipa/66598"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12002",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-jamaican-haze/3736988",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド ブルワリー",
            "beer_name_en": "Jamaican Haze",
            "beer_name_jp": "ジャマイカン ヘイズ",
            "beer_name_core": "Jamaican Haze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-jamaican-haze/3736988"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12004",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-blueberry-wheat/4542419",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド ブルワリー",
            "beer_name_en": "Blueberry Wheat",
            "beer_name_jp": "ブルーベリー ウィート",
            "beer_name_core": "Blueberry Wheat",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-blueberry-wheat/4542419"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b128-c12007",
        "untappd_url": "https://untappd.com/b/hinterland-brewery-packerland-pilsner/501979",
        "gemini_update": {
            "brewery_name_en": "Hinterland Brewery",
            "brewery_name_jp": "ヒンターランド ブルワリー",
            "beer_name_en": "Packerland Pilsner",
            "beer_name_jp": "パッカーランド・ピルスナー",
            "beer_name_core": "Packerland Pilsner",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/hinterland-brewery-packerland-pilsner/501979"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b113-b50025",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-black-currant-layla/2851901",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘビーリフ ブルーイング",
            "beer_name_en": "Black Currant Layla",
            "beer_name_jp": "ブラック キュラント レイラ",
            "beer_name_core": "Black Currant Layla",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-black-currant-layla/2851901"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b113-b50026",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-dear-agony-willett-rye-barrel-aged-2021/4671126",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘビーリフ ブルーイング",
            "beer_name_en": "Dear Agony - Willett Rye Barrel Aged (2021)",
            "beer_name_jp": "ディア アゴニー (ウィレット ライ バレル エイジド 2021)",
            "beer_name_core": "Dear Agony Willett Rye Barrel Aged 2021",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-dear-agony-willett-rye-barrel-aged-2021/4671126"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b113-c16015",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-hat-dance/3640739",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘビーリフ ブルーイング",
            "beer_name_en": "Hat Dance",
            "beer_name_jp": "ハットダンス",
            "beer_name_core": "Hat Dance",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-hat-dance/3640739"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b113-c16016",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-raglan-irish-red/608392",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘビーリフ ブルーイング",
            "beer_name_en": "Raglan Irish Red",
            "beer_name_jp": "ラグラン アイリッシュ レッド",
            "beer_name_core": "Raglan Irish Red",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-raglan-irish-red/608392"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b113-c16023",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-n-i-b/5487271",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘビーリフ ブルーイング",
            "beer_name_en": "N.I.B.",
            "beer_name_jp": "NIB ヘイジーセッションエール",
            "beer_name_core": "N.I.B.",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-n-i-b/5487271"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b113-c16024",
        "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-daisy-glaze/2459386",
        "gemini_update": {
            "brewery_name_en": "Heavy Riff Brewing Company",
            "brewery_name_jp": "ヘビーリフ ブルーイング",
            "beer_name_en": "Daisy Glaze",
            "beer_name_jp": "デイジー グレイズ",
            "beer_name_core": "Daisy Glaze",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/heavy-riff-brewing-company-daisy-glaze/2459386"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b129-c16007",
        "untappd_url": "https://untappd.com/b/mother-road-brewing-company-double-6-american-beer/5858018",
        "gemini_update": {
            "brewery_name_en": "Mother Road Brewing Company",
            "brewery_name_jp": "マザーロード ブルーイング",
            "beer_name_en": "Double 6 American Beer",
            "beer_name_jp": "ダブルシックス",
            "beer_name_core": "Double 6 American Beer",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mother-road-brewing-company-double-6-american-beer/5858018"
        }
    },

    # --- 未紐付け在庫ビールから調査特定した5件 ---
    {
        "url": "https://www.antenna-america.com/products/b039-c16005",
        "untappd_url": "https://untappd.com/b/49th-state-brewing-smok/4106165",
        "gemini_update": {
            "brewery_name_en": "49th State Brewing",
            "brewery_name_jp": "フォーティナインス ステート ブルーイング",
            "beer_name_en": "Smōk",
            "beer_name_jp": "スモーク",
            "beer_name_core": "Smok",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/49th-state-brewing-smok/4106165"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b039-c12001",
        "untappd_url": "https://untappd.com/b/49th-state-brewing-solstice-ipa/192380",
        "gemini_update": {
            "brewery_name_en": "49th State Brewing",
            "brewery_name_jp": "フォーティナインス ステート ブルーイング",
            "beer_name_en": "Solstice IPA",
            "beer_name_jp": "ソルスティス IPA",
            "beer_name_core": "Solstice IPA",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/49th-state-brewing-solstice-ipa/192380"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b114-c16014",
        "untappd_url": "https://untappd.com/b/embolden-beer-company-dawn-in-ube/6202152",
        "gemini_update": {
            "brewery_name_en": "Embolden Beer Company",
            "brewery_name_jp": "エンボルデン ビア カンパニー",
            "beer_name_en": "Dawn In Ube",
            "beer_name_jp": "ショーグン・ドーン・イン・ウベ",
            "beer_name_core": "Dawn In Ube",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/embolden-beer-company-dawn-in-ube/6202152"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b039-c16007",
        "untappd_url": "https://untappd.com/b/49th-state-brewing-tropical-tundra/6357034",
        "gemini_update": {
            "brewery_name_en": "49th State Brewing",
            "brewery_name_jp": "フォーティナインス ステート ブルーイング",
            "beer_name_en": "Tropical Tundra",
            "beer_name_jp": "トロピカ タンドラ",
            "beer_name_core": "Tropical Tundra",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/49th-state-brewing-tropical-tundra/6357034"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b129-c12010",
        "untappd_url": "https://untappd.com/b/mother-road-brewing-company-america-250-arizona-lager/6599825",
        "gemini_update": {
            "brewery_name_en": "Mother Road Brewing Company",
            "brewery_name_jp": "マザーロード ブルーイング",
            "beer_name_en": "America 250 Arizona Lager",
            "beer_name_jp": "アリゾナ250",
            "beer_name_core": "America 250 Arizona Lager",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/mother-road-brewing-company-america-250-arizona-lager/6599825"
        }
    }
]

# 2. ローリング巡回・Untappd データの最新化対象 (5件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/8-wired-whisky-sour-barrel-aged-sour-ale/6459546",
    "https://untappd.com/b/tonewood-brewing-slow-saison-vol-2/5759277",
    "https://untappd.com/b/monkish-brewing-co-sixteen-trees/6385840",
    "https://untappd.com/b/stone-brewing-stone-dayfest/6223638",
    "https://untappd.com/b/long-beach-beer-lab-this-is-the-way-ipa/4830447"
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

    # 3. マテリアライズドビューのリフレッシュ
    logger.info("\n[3] Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

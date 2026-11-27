import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 1. 新規エンリッチ商品（未エンリッチ20件 + 未紐付け特定2件 = 計22件）
NEW_ENRICH_ITEMS = [
    # --- 未エンリッチ商品 (最優先) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8205",
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8236",
        "untappd_url": "https://untappd.com/b/talea-beer-co-basically-pumpkin/4501574",
        "gemini_update": {
            "brewery_name_en": "TALEA Beer Co.",
            "brewery_name_jp": "タレイアビア",
            "beer_name_en": "Basically Pumpkin",
            "beer_name_jp": "ベーシカリー パンプキン",
            "beer_name_core": "Basically Pumpkin",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/talea-beer-co-basically-pumpkin/4501574"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8234",
        "untappd_url": "https://untappd.com/b/talea-beer-co-fresh-coast/5392212",
        "gemini_update": {
            "brewery_name_en": "TALEA Beer Co.",
            "brewery_name_jp": "タレイアビア",
            "beer_name_en": "Fresh Coast",
            "beer_name_jp": "フレッシュコースト",
            "beer_name_core": "Fresh Coast",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/talea-beer-co-fresh-coast/5392212"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8233",
        "untappd_url": "https://untappd.com/b/talea-beer-co-sun-up/3180072",
        "gemini_update": {
            "brewery_name_en": "TALEA Beer Co.",
            "brewery_name_jp": "タレイアビア",
            "beer_name_en": "Sun Up",
            "beer_name_jp": "サン アップ",
            "beer_name_core": "Sun Up",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/talea-beer-co-sun-up/3180072"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8232",
        "untappd_url": "https://untappd.com/b/talea-beer-co-al-dente/4330878",
        "gemini_update": {
            "brewery_name_en": "TALEA Beer Co.",
            "brewery_name_jp": "タレイアビア",
            "beer_name_en": "Al Dente",
            "beer_name_jp": "アルデンテ",
            "beer_name_core": "Al Dente",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/talea-beer-co-al-dente/4330878"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8231",
        "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-zed-lupulin/2253802",
        "gemini_update": {
            "brewery_name_en": "Kings County Brewers Collective",
            "brewery_name_jp": "キングスカウンティ ブルワーズ コレクティブ",
            "beer_name_en": "Zed Lupulin",
            "beer_name_jp": "ゼッド ルプリン",
            "beer_name_core": "Zed Lupulin",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-zed-lupulin/2253802"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8230",
        "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-school-of-croc/5495176",
        "gemini_update": {
            "brewery_name_en": "Kings County Brewers Collective",
            "brewery_name_jp": "キングスカウンティ ブルワーズ コレクティブ",
            "beer_name_en": "School of Croc",
            "beer_name_jp": "スクール オブ クロック",
            "beer_name_core": "School of Croc",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-school-of-croc/5495176"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8229",
        "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-beetlegoose/5977125",
        "gemini_update": {
            "brewery_name_en": "Kings County Brewers Collective",
            "brewery_name_jp": "キングスカウンティ ブルワーズ コレクティブ",
            "beer_name_en": "Beetlegoose",
            "beer_name_jp": "ビートルグース",
            "beer_name_core": "Beetlegoose",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-beetlegoose/5977125"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=1901",
        "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-superhero-sidekicks/2877472",
        "gemini_update": {
            "brewery_name_en": "Kings County Brewers Collective",
            "brewery_name_jp": "キングスカウンティ ブルワーズ コレクティブ",
            "beer_name_en": "Superhero Sidekicks",
            "beer_name_jp": "スーパーヒーロー サイドキックス",
            "beer_name_core": "Superhero Sidekicks",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-superhero-sidekicks/2877472"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8228",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-screwdriver/6666895",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Screwdriver",
            "beer_name_jp": "スクリュードライバー",
            "beer_name_core": "Screwdriver",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-screwdriver/6666895"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8227",
        "untappd_url": "https://untappd.com/b/industrial-arts-brewing-week-521-space-wrench/6765460",
        "gemini_update": {
            "brewery_name_en": "Industrial Arts Brewing",
            "brewery_name_jp": "インダストリアルアーツ",
            "beer_name_en": "Week 521 Space Wrench",
            "beer_name_jp": "ウィーク521 スペース レンチ",
            "beer_name_core": "Week 521 Space Wrench",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/industrial-arts-brewing-week-521-space-wrench/6765460"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8226",
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
        "url": "https://www.arome.jp/products/detail.php?product_id=8242",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-dithyramb/6520609",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Dithyramb",
            "beer_name_jp": "ディシラム",
            "beer_name_core": "Dithyramb",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-dithyramb/6520609"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8241",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-blue-velvet/6760093",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Blue Velvet",
            "beer_name_jp": "ブルー ベルベット",
            "beer_name_core": "Blue Velvet",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-blue-velvet/6760093"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8240",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-color-field/4245101",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Color Field",
            "beer_name_jp": "カラーフィールド",
            "beer_name_core": "Color Field",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-color-field/4245101"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8239",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-nothing-but-nelson/6125976",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Nothing But Nelson",
            "beer_name_jp": "ナッシング バット ネルソン",
            "beer_name_core": "Nothing But Nelson",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-nothing-but-nelson/6125976"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8238",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-zero-coast/4431073",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Zero Coast",
            "beer_name_jp": "ゼロ コースト",
            "beer_name_core": "Zero Coast",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-zero-coast/4431073"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8237",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-invisible-touch/3730072",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Invisible Touch",
            "beer_name_jp": "インヴィジブル タッチ",
            "beer_name_core": "Invisible Touch",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-invisible-touch/3730072"
        }
    },
    {
        "url": "https://beervolta.com/?pid=194169591",
        "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-zero-coast/4431073",
        "gemini_update": {
            "brewery_name_en": "Grimm Artisanal Ales",
            "brewery_name_jp": "グリム",
            "beer_name_en": "Zero Coast",
            "beer_name_jp": "ゼロ コースト",
            "beer_name_core": "Zero Coast",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grimm-artisanal-ales-zero-coast/4431073"
        }
    },
    {
        "url": "https://151l.shop/?pid=194060734",
        "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-breaking-bud/929842",
        "gemini_update": {
            "brewery_name_en": "Knee Deep Brewing Company",
            "brewery_name_jp": "ニーディープ",
            "beer_name_en": "Breaking Bud",
            "beer_name_jp": "ブレイキング バド",
            "beer_name_core": "Breaking Bud",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/knee-deep-brewing-company-breaking-bud/929842"
        }
    },

    # --- 未紐付けから特定したアイテム ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6701",
        "untappd_url": "https://untappd.com/b/grains-of-wrath-built-for-speed/3629186",
        "gemini_update": {
            "brewery_name_en": "Grains of Wrath",
            "brewery_name_jp": "グレインズ オブ ラス",
            "beer_name_en": "Built for Speed",
            "beer_name_jp": "ビルト フォー スピード",
            "beer_name_core": "Built for Speed",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grains-of-wrath-built-for-speed/3629186"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6056",
        "untappd_url": "https://untappd.com/b/grains-of-wrath-destination-funeral/5912416",
        "gemini_update": {
            "brewery_name_en": "Grains of Wrath",
            "brewery_name_jp": "グレインズ オブ ラス",
            "beer_name_en": "Destination Funeral",
            "beer_name_jp": "デスティネーション フューネラル",
            "beer_name_core": "Destination Funeral",
            "product_type": "beer",
            "is_set": False,
            "untappd_url": "https://untappd.com/b/grains-of-wrath-destination-funeral/5912416"
        }
    }
]

# 2. 未登録確認済み・調査タイムスタンプ更新対象 (Untappd未登録のビール)
UNREGISTERED_INSPECTED_URLS = [
    "https://www.arome.jp/products/detail.php?product_id=8208",   # VERTERE / Cotinus
    "https://151l.shop/?pid=193631430",                          # Farmentry / OCHA! YAMATO
    "https://151l.shop/?pid=192919839"                           # ISEKADOYA / KADOLABO 039
]

# 3. ローリング巡回・Untappd データの最新化対象 (5件)
BEER_REFRESH_URLS = [
    "https://untappd.com/b/knee-deep-brewing-company-tahoe-deep/1914830",
    "https://untappd.com/b/industrial-arts-brewing-wrench-neipa/2234085",
    "https://untappd.com/b/knee-deep-brewing-company-hoptologist/81914",
    "https://untappd.com/b/knee-deep-brewing-company-simtra-triple-ipa/93848",
    "https://untappd.com/b/knee-deep-brewing-company-breaking-bud/929842"
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

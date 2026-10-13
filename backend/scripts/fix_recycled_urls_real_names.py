"""
Correct recycled URLs in arome and chouseiya to match current product titles.
"""
import asyncio
import logging
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.core.utils import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RECYCLED_FIXES = [
    # 1. arome 7433 (現在: アンサング / メタプレックス - In Stock)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7433",
        "untappd_url": "https://untappd.com/b/unsung-brewing-co-metaplex/2076879",
        "gemini": {
            "brewery_name_en": "Unsung Brewing Co",
            "brewery_name_jp": "アンサングブリューイング",
            "beer_name_en": "MetaPlex",
            "beer_name_jp": "メタプレックス",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/unsung-brewing-co-metaplex/2076879"
        }
    },
    # 2. arome 6943 (現在: ヴォンエバート / ボラタイル・サブスタンス - In Stock)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6943",
        "untappd_url": "https://untappd.com/b/von-ebert-brewing-volatile-substance/2625292",
        "gemini": {
            "brewery_name_en": "Von Ebert Brewing",
            "brewery_name_jp": "ヴォンエバート",
            "beer_name_en": "Volatile Substance",
            "beer_name_jp": "ボラタイル・サブスタンス",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/von-ebert-brewing-volatile-substance/2625292"
        }
    },
    # 3. arome 6454 (現在: ノボルブルーイング / ノセル)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6454",
        "untappd_url": None,  # Untappd未登録
        "gemini": {
            "brewery_name_en": "Novoru Brewing",
            "brewery_name_jp": "ノボルブルーイング",
            "beer_name_en": "Noseru",
            "beer_name_jp": "ノセル",
            "product_type": "beer",
            "untappd_url": None
        }
    },
    # 4. arome 6492 (現在: エイトワイヤード / ホップサラダ)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6492",
        "untappd_url": "https://untappd.com/b/8-wired-hop-salad/5354972",
        "gemini": {
            "brewery_name_en": "8 Wired Brewing",
            "brewery_name_jp": "エイトワイヤード",
            "beer_name_en": "Hop Salad",
            "beer_name_jp": "ホップサラダ",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/8-wired-hop-salad/5354972"
        }
    },
    # 5. arome 6912 (現在: グリーンチーク / スーツケース・オブ・ユズ)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6912",
        "untappd_url": "https://untappd.com/b/green-cheek-beer-company-suitcases-of-yuzu/6559357",
        "gemini": {
            "brewery_name_en": "Green Cheek Beer Co.",
            "brewery_name_jp": "グリーンチーク",
            "beer_name_en": "Suitcases Of Yuzu",
            "beer_name_jp": "スーツケース・オブ・ユズ",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/green-cheek-beer-company-suitcases-of-yuzu/6559357"
        }
    },
    # 6. arome 7016 (現在: クラウドウォーター / ウェストコーストアイピーエー・イズ・デッド)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7016",
        "untappd_url": "https://untappd.com/b/cloudwater-brew-co-west-coast-ipa-is-dead/5109275",
        "gemini": {
            "brewery_name_en": "Cloudwater Brew Co.",
            "brewery_name_jp": "クラウドウォーター",
            "beer_name_en": "West Coast IPA Is Dead",
            "beer_name_jp": "ウェストコーストアイピーエー・イズ・デッド",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/cloudwater-brew-co-west-coast-ipa-is-dead/5109275"
        }
    },
    # 7. arome 7390 (現在: ブラックレイヴン / ウェストコーストIPA)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7390",
        "untappd_url": "https://untappd.com/b/black-raven-brewing-west-coast-ipa/5248899",
        "gemini": {
            "brewery_name_en": "Black Raven Brewing Company",
            "brewery_name_jp": "ブラックレイヴン",
            "beer_name_en": "West Coast IPA",
            "beer_name_jp": "ウェストコーストIPA",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/black-raven-brewing-west-coast-ipa/5248899"
        }
    },
    # 8. arome 7015 (現在: クラウドウォーター / ラグランロード)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7015",
        "untappd_url": "https://untappd.com/b/cloudwater-brew-co-raglan-road/6496304",
        "gemini": {
            "brewery_name_en": "Cloudwater Brew Co.",
            "beer_name_en": "Raglan Road",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/cloudwater-brew-co-raglan-road/6496304"
        }
    },
    # 9. arome 7014 (現在: クラウドウォーター / ソリッド・レイディアス)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7014",
        "untappd_url": "https://untappd.com/b/cloudwater-brew-co-solis-radius/6515812",
        "gemini": {
            "brewery_name_en": "Cloudwater Brew Co.",
            "beer_name_en": "Solis Radius",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/cloudwater-brew-co-solis-radius/6515812"
        }
    },
    # 10. arome 6906 (現在: ビーチウッド / モカ・マシン)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6906",
        "untappd_url": "https://untappd.com/b/beachwood-brewing-mocha-machine/322703",
        "gemini": {
            "brewery_name_en": "Beachwood Brewing",
            "beer_name_en": "Mocha Machine",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/beachwood-brewing-mocha-machine/322703"
        }
    },
    # 11. arome 6905 (現在: リヴィジョン / ウィングティップ)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6905",
        "untappd_url": "https://untappd.com/b/revision-brewing-company-wing-tip/5121730",
        "gemini": {
            "brewery_name_en": "Revision Brewing Company",
            "beer_name_en": "Wing Tip",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/revision-brewing-company-wing-tip/5121730"
        }
    },
    # 12. ちょうせいや 3058 (現在: 【ease off/AMAKUSA SONAR】)
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003058",
        "untappd_url": "https://untappd.com/b/amakusa-sonar-beer-ease-off/6287731",
        "gemini": {
            "brewery_name_en": "AMAKUSA SONAR BEER",
            "brewery_name_jp": "アマクサソナービール",
            "beer_name_en": "ease off",
            "beer_name_jp": "イーズオフ",
            "product_type": "beer",
            "untappd_url": "https://untappd.com/b/amakusa-sonar-beer-ease-off/6287731"
        }
    }
]

async def run_recycled_fixes():
    supabase = get_supabase_client()
    logger.info(f"Applying {len(RECYCLED_FIXES)} recycled URL fixes...")

    untappd_details_cache = {}

    for fix in RECYCLED_FIXES:
        p_url = fix["url"]
        u_url = fix["untappd_url"]
        gemini = fix.get("gemini")

        logger.info(f"\nProcessing product URL: {p_url}")

        if u_url:
            if u_url not in untappd_details_cache:
                logger.info(f"  Scraping details for {u_url}...")
                details = await scrape_beer_details(u_url)
                untappd_details_cache[u_url] = details
                await asyncio.sleep(1.0)
            else:
                details = untappd_details_cache[u_url]

            if details and details.get('untappd_beer_name'):
                payload = map_details_to_payload(details)
                payload['untappd_url'] = u_url
                supabase.table('untappd_data').upsert(payload, on_conflict='untappd_url').execute()
                logger.info(f"  ✅ Upserted untappd_data: {details.get('untappd_brewery_name')} / {details.get('untappd_beer_name')}")

            # Update scraped_beers
            supabase.table('scraped_beers').update({'untappd_url': u_url}).eq('url', p_url).execute()
            logger.info(f"  ✅ Updated scraped_beers with untappd_url: {u_url}")
        else:
            supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', p_url).execute()
            logger.info(f"  ✅ Cleared untappd_url in scraped_beers for {p_url}")

        if gemini:
            chk = supabase.table('gemini_data').select('url').eq('url', p_url).execute()
            gemini_payload = {**gemini, 'url': p_url}
            if chk.data:
                supabase.table('gemini_data').update(gemini_payload).eq('url', p_url).execute()
                logger.info(f"  ✅ Updated gemini_data: {gemini_payload}")
            else:
                supabase.table('gemini_data').insert(gemini_payload).execute()
                logger.info(f"  ✅ Inserted gemini_data: {gemini_payload}")

    refresh_materialized_view(supabase, logger)
    logger.info("🎉 All recycled URL fixes applied and view refreshed!")

if __name__ == '__main__':
    asyncio.run(run_recycled_fixes())

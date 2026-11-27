"""
Batch Untappd audit & fix script for 2026-11-27.
Applies 23 verified fixes:
- 4 misassigned links corrected
- 2 product_type misclassifications fixed (glass/set -> beer) and linked
- 1 duplicate Untappd ID URL slug unified
- 12 cross-store unlinked beers linked
- 4 newly discovered unlinked beers scraped & linked
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.core.utils import map_details_to_payload
from backend.src.services.untappd.http_client import close_async_client, scrape_beer_details

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Untappd URLs whose master metadata should be scraped/upserted into untappd_data
UNTAPPD_SCRAPE_URLS = [
    "https://untappd.com/b/vertere-window-to-wcb-2026-hazy-dipa/7698752",
    "https://untappd.com/b/geuzestekerij-de-cam-geuze-2019/3427005",
    "https://untappd.com/b/kyoto-brewing-company-red-delorean/6928518",
    "https://untappd.com/b/coldfire-brewing-tangle-of-tigers-epic-fall-2026/6921154",
    "https://untappd.com/b/tamamura-honten-co-yama-bushi-5-fresh-hop-saison/7629205",
    "https://untappd.com/b/farmentry-ocha-yamato/7695709",
]

FIX_ITEMS = [
    # --- A. Misassigned links (4) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8468",
        "untappd_url": "https://untappd.com/b/vertere-window-to-wcb-2026-hazy-dipa/7698752",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Window To WCB 2026 Hazy DIPA",
            "beer_name_jp": "ウィンドウ・トゥ・WCB 2026 ヘイジーダブルIPA",
            "beer_name_core": "Window To WCB 2026 Hazy DIPA",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://151l.shop/?pid=194902005",
        "untappd_url": "https://untappd.com/b/vertere-window-to-wcb-2026-hazy-dipa/7698752",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Window To WCB 2026 Hazy DIPA",
            "beer_name_jp": "ウィンドウズトゥWCB2026 ヘイジーダブル",
            "beer_name_core": "Window To WCB 2026 Hazy DIPA",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://151l.shop/?pid=194903769",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-window-to-vertere-2026-sour/7695398",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウエストコーストブルーイング",
            "beer_name_en": "Window to VERTERE 2026 (Sour)",
            "beer_name_jp": "ウィンドウズトゥバテレ2026 プラムサワー",
            "beer_name_core": "Window to VERTERE 2026 (Sour)",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=1906",
        "untappd_url": "https://untappd.com/b/geuzestekerij-de-cam-geuze-2019/3427005",
        "gemini_update": {
            "brewery_name_en": "Geuzestekerij De Cam",
            "brewery_name_jp": "デ カム",
            "beer_name_en": "Geuze (2019)",
            "beer_name_jp": "2019 グーズ",
            "beer_name_core": "Geuze (2019)",
            "product_type": "beer",
            "is_set": False,
        },
    },
    # --- B. product_type misclassifications (2) ---
    {
        "url": "https://beervolta.com/?pid=194696228",
        "untappd_url": "https://untappd.com/b/evil-twin-brewing-nyc-even-more-grasp/3170901",
        "gemini_update": {
            "brewery_name_en": "Evil Twin Brewing NYC",
            "brewery_name_jp": "イーヴルツイン",
            "beer_name_en": "Even More Grasp",
            "beer_name_jp": "イーブン モア グラスプ",
            "beer_name_core": "Even More Grasp",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://151l.shop/?pid=194301205",
        "untappd_url": "https://untappd.com/b/kyoto-brewing-company-red-delorean/6928518",
        "gemini_update": {
            "brewery_name_en": "Kyoto Brewing Company",
            "brewery_name_jp": "京都醸造",
            "beer_name_en": "Red Delorean",
            "beer_name_jp": "未来よりの使者",
            "beer_name_core": "Red Delorean",
            "product_type": "beer",
            "is_set": False,
        },
    },
    # --- C. Duplicate Untappd ID URL slug unification (1) ---
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8454",
        "untappd_url": "https://untappd.com/b/monkish-brewing-co-monkish-shinjuku/7695580",
        "gemini_update": {
            "brewery_name_en": "Monkish Brewing Co.",
            "brewery_name_jp": "モンキッシュ",
            "beer_name_en": "Monkish Shinjuku",
            "beer_name_jp": "シンジュク",
            "beer_name_core": "Monkish Shinjuku",
            "product_type": "beer",
            "is_set": False,
        },
    },
    # --- D. Cross-store linkable beers (12) ---
    {
        "url": "https://maruho.shop/products/fluffhead-473ml-block-15",
        "untappd_url": "https://untappd.com/b/block-15-brewing-company-fluffhead/1663063",
        "gemini_update": {
            "brewery_name_en": "Block 15 Brewing Company",
            "brewery_name_jp": "ブロック15",
            "beer_name_en": "Fluffhead",
            "beer_name_core": "Fluffhead",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/deep-seek-473ml-block-15",
        "untappd_url": "https://untappd.com/b/block-15-brewing-company-deep-seek/5128453",
        "gemini_update": {
            "brewery_name_en": "Block 15 Brewing Company",
            "brewery_name_jp": "ブロック15",
            "beer_name_en": "Deep Seek",
            "beer_name_core": "Deep Seek",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/sticky-hands-473ml-block-15",
        "untappd_url": "https://untappd.com/b/block-15-brewing-company-sticky-hands/303588",
        "gemini_update": {
            "brewery_name_en": "Block 15 Brewing Company",
            "brewery_name_jp": "ブロック15",
            "beer_name_en": "Sticky Hands",
            "beer_name_core": "Sticky Hands",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/ridgeback-red-473ml-block-15",
        "untappd_url": "https://untappd.com/b/block-15-brewing-company-ridgeback-red/44245",
        "gemini_update": {
            "brewery_name_en": "Block 15 Brewing Company",
            "brewery_name_jp": "ブロック15",
            "beer_name_en": "Ridgeback Red",
            "beer_name_core": "Ridgeback Red",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/gloria-473ml-block-15",
        "untappd_url": "https://untappd.com/b/block-15-brewing-company-gloria/1179286",
        "gemini_update": {
            "brewery_name_en": "Block 15 Brewing Company",
            "brewery_name_jp": "ブロック15",
            "beer_name_en": "Gloria!",
            "beer_name_core": "Gloria!",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/nebula-473ml-block-15",
        "untappd_url": "https://untappd.com/b/block-15-brewing-company-nebula/13644",
        "gemini_update": {
            "brewery_name_en": "Block 15 Brewing Company",
            "brewery_name_jp": "ブロック15",
            "beer_name_en": "Nebula",
            "beer_name_core": "Nebula",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/death-greets-me-warm-collab-w-messorem-473ml-lyric",
        "untappd_url": "https://untappd.com/b/lyric-brewing-company-death-greets-me-warm/7187555",
        "gemini_update": {
            "brewery_name_en": "Lyric Brewing Company",
            "brewery_name_jp": "リリック",
            "beer_name_en": "Death Greets Me Warm",
            "beer_name_core": "Death Greets Me Warm",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/music-of-the-spheres-collab-w-rar-473ml-test",
        "untappd_url": "https://untappd.com/b/test-music-of-the-spheres/7609930",
        "gemini_update": {
            "brewery_name_en": "TEST",
            "brewery_name_jp": "テスト",
            "beer_name_en": "Music of the Spheres",
            "beer_name_core": "Music of the Spheres",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://beervolta.com/?pid=194912090",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-window-to-vertere-2026-hazy/7695399",
        "gemini_update": {
            "brewery_name_en": "West Coast Brewing",
            "brewery_name_jp": "ウェストコースト",
            "beer_name_en": "Window to VERTERE 2026 (Hazy)",
            "beer_name_jp": "ウィンドウ トゥ バテレ",
            "beer_name_core": "Window to VERTERE 2026 (Hazy)",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://beervolta.com/?pid=194696220",
        "untappd_url": "https://untappd.com/b/evil-twin-brewing-nyc-thirst-that-doesn-t-apologize/6852801",
        "gemini_update": {
            "brewery_name_en": "Evil Twin Brewing NYC",
            "brewery_name_jp": "イーヴルツイン",
            "beer_name_en": "THIRST THAT DOESN'T APOLOGIZE",
            "beer_name_jp": "サースト ザット ダズント アポロジャイズ",
            "beer_name_core": "THIRST THAT DOESN'T APOLOGIZE",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://beervolta.com/?pid=194696219",
        "untappd_url": "https://untappd.com/b/evil-twin-brewing-nyc-this-ipa-doesn-t-care-about-your-feelings/6836081",
        "gemini_update": {
            "brewery_name_en": "Evil Twin Brewing NYC",
            "brewery_name_jp": "イーヴルツイン",
            "beer_name_en": "THIS IPA DOESN'T CARE ABOUT YOUR FEELINGS",
            "beer_name_jp": "ディス IPA ダズント ケア アバウト ユア フィーリングス",
            "beer_name_core": "THIS IPA DOESN'T CARE ABOUT YOUR FEELINGS",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8449",
        "untappd_url": "https://untappd.com/b/evil-twin-brewing-nyc-even-more-grasp/3170901",
        "gemini_update": {
            "brewery_name_en": "Evil Twin Brewing NYC",
            "brewery_name_jp": "イーブルツイン",
            "beer_name_en": "Even More Grasp",
            "beer_name_jp": "イーブン・モア・グラスプ",
            "beer_name_core": "Even More Grasp",
            "product_type": "beer",
            "is_set": False,
        },
    },
    # --- E. Newly discovered unlinked beers (4) ---
    {
        "url": "https://beervolta.com/?pid=194912092",
        "untappd_url": "https://untappd.com/b/vertere-window-to-wcb-2026-hazy-dipa/7698752",
        "gemini_update": {
            "brewery_name_en": "VERTERE",
            "brewery_name_jp": "バテレ",
            "beer_name_en": "Window To WCB 2026 Hazy DIPA",
            "beer_name_jp": "ウィンドウ WCB",
            "beer_name_core": "Window To WCB 2026 Hazy DIPA",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8411",
        "untappd_url": "https://untappd.com/b/coldfire-brewing-tangle-of-tigers-epic-fall-2026/6921154",
        "gemini_update": {
            "brewery_name_en": "ColdFire Brewing",
            "brewery_name_jp": "コールドファイア",
            "beer_name_en": "Tangle of Tigers: Epic (Fall 2026)",
            "beer_name_jp": "タングル・オブ・タイガーズ - エピックエディション",
            "beer_name_core": "Tangle of Tigers: Epic",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://maruho.shop/products/山伏-伍-fresh-hop-saison-750ml-志賀高原ビール",
        "untappd_url": "https://untappd.com/b/tamamura-honten-co-yama-bushi-5-fresh-hop-saison/7629205",
        "gemini_update": {
            "brewery_name_en": "Tamamura Honten Co.",
            "brewery_name_jp": "志賀高原ビール",
            "beer_name_en": "Yama-Bushi 5 fresh hop saison",
            "beer_name_jp": "山伏 伍 Fresh Hop Saison",
            "beer_name_core": "Yama-Bushi 5 fresh hop saison",
            "product_type": "beer",
            "is_set": False,
        },
    },
    {
        "url": "https://151l.shop/?pid=193631430",
        "untappd_url": "https://untappd.com/b/farmentry-ocha-yamato/7695709",
        "gemini_update": {
            "brewery_name_en": "Farmentry",
            "brewery_name_jp": "ファーメンタリー",
            "beer_name_en": "Ocha! - Yamato -",
            "beer_name_jp": "お茶！大和",
            "beer_name_core": "Ocha! Yamato",
            "product_type": "beer",
            "is_set": False,
        },
    },
]


def run_db_op(op_func, max_retries=3, delay=1.0):
    for attempt in range(max_retries):
        try:
            return op_func()
        except Exception as e:
            logger.warning(f"DB op failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (attempt + 1))


async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("[1] Scraping and upserting Untappd master details...")
    for untappd_url in UNTAPPD_SCRAPE_URLS:
        details = await scrape_beer_details(untappd_url)
        if details and details.get("untappd_beer_name"):
            payload = map_details_to_payload(details)
            payload["untappd_url"] = untappd_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda p=payload: sync_execute(sb.table("untappd_data").upsert(p, on_conflict="untappd_url")))
            logger.info(f"  Upserted: [{details.get('untappd_brewery_name')}] {details.get('untappd_beer_name')}")
        else:
            logger.warning(f"  Failed to scrape details for {untappd_url}")
        await asyncio.sleep(0.4)

    await close_async_client()

    logger.info(f"[2] Updating {len(FIX_ITEMS)} items in gemini_data and scraped_beers...")
    for item in FIX_ITEMS:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = dict(item["gemini_update"])
        gem_update["url"] = url
        gem_update["untappd_url"] = untappd_url
        gem_update["updated_at"] = now_iso

        run_db_op(lambda g=gem_update: sync_execute(sb.table("gemini_data").upsert(g, on_conflict="url")))
        run_db_op(
            lambda u=url, uu=untappd_url: sync_execute(
                sb.table("scraped_beers")
                .update({"untappd_url": uu, "untappd_enriched_at": now_iso})
                .eq("url", u)
            )
        )
        logger.info(f"  Updated {url} -> {untappd_url}")

    logger.info("[3] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())

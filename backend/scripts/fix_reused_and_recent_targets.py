"""
Script to apply fixes for reused URLs, brewery alias pollution, and recent Untappd mismatches.
Created during inspection on 2026-10-13.
"""
import asyncio
import logging
from datetime import datetime, timezone
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FIXES = [
    # 1. 伊勢角屋麦酒 (誤抽出・未マッチ解消)
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001986",
        "untappd_url": "https://untappd.com/b/isekado/7176491",
        "gemini": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Smoked Dashi",
            "beer_name_jp": "燻しだし",
            "untappd_url": "https://untappd.com/b/isekado/7176491"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001504",
        "untappd_url": "https://untappd.com/b/isekado/6455614",
        "gemini": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Neko no Nomimono",
            "beer_name_jp": "ねこののみもの",
            "untappd_url": "https://untappd.com/b/isekado/6455614"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002814",
        "untappd_url": "https://untappd.com/b/isekado-jungle-fantasy/6366593",
        "gemini": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Jungle Fantasy",
            "beer_name_jp": "ジャングルファンタジー",
            "untappd_url": "https://untappd.com/b/isekado-jungle-fantasy/6366593"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002630",
        "untappd_url": "https://untappd.com/b/isekado-hop-nyaon-13th-fleet-13/6972729",
        "gemini": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "HOP NYAON 13th Fleet",
            "beer_name_jp": "ホップにゃおん第13艦隊",
            "untappd_url": "https://untappd.com/b/isekado-hop-nyaon-13th-fleet-13/6972729"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003331",
        "untappd_url": "https://untappd.com/b/isekado-ipa/6927586",
        "gemini": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "beer_name_en": "Nikukyu IPA Returns",
            "beer_name_jp": "にくきゅうIPAリターンズ",
            "untappd_url": "https://untappd.com/b/isekado-ipa/6927586"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003362",
        "untappd_url": None,
        "gemini": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
        }
    },
    # 2. ショップURL再利用（リサイクル）アイテムの是正
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000589",
        "untappd_url": "https://untappd.com/b/totopia-brewery-lostphobia/6999158",
        "gemini": {
            "brewery_name_en": "Totopia Brewery",
            "brewery_name_jp": "トトピアブルワリー",
            "beer_name_en": "Lostphobia",
            "beer_name_jp": "Lostphobia",
            "untappd_url": "https://untappd.com/b/totopia-brewery-lostphobia/6999158"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000795",
        "untappd_url": "https://untappd.com/b/break-edge-beer-works-awake/6986040",
        "gemini": {
            "brewery_name_en": "BREAK EDGE BEER WORKS",
            "brewery_name_jp": "ブレイクエッジビアワークス",
            "beer_name_en": "AWAKE",
            "beer_name_jp": "AWAKE",
            "untappd_url": "https://untappd.com/b/break-edge-beer-works-awake/6986040"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000678",
        "untappd_url": "https://untappd.com/b/uchu-brewing-the-dark-side-of-the-moon/6978164",
        "gemini": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "The Dark Side of the Moon",
            "beer_name_jp": "The Dark Side of the Moon",
            "untappd_url": "https://untappd.com/b/uchu-brewing-the-dark-side-of-the-moon/6978164"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002902",
        "untappd_url": "https://untappd.com/b/nobody-brewing-rough-trade-ipa/6861725",
        "gemini": {
            "brewery_name_en": "Nobody Brewing",
            "brewery_name_jp": "ノーバディブルーイング",
            "beer_name_en": "Rough Trade IPA",
            "beer_name_jp": "Rough Trade IPA",
            "untappd_url": "https://untappd.com/b/nobody-brewing-rough-trade-ipa/6861725"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002975",
        "untappd_url": "https://untappd.com/b/inkhorn-brewing-eutopos/6921700",
        "gemini": {
            "brewery_name_en": "Inkhorn Brewing",
            "brewery_name_jp": "インクホーンブルーイング",
            "beer_name_en": "Eutopos",
            "beer_name_jp": "Eutopos",
            "untappd_url": "https://untappd.com/b/inkhorn-brewing-eutopos/6921700"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000963",
        "untappd_url": "https://untappd.com/b/uchu-brewing-space-punch/6042400",
        "gemini": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "Space Punch",
            "beer_name_jp": "Space Punch",
            "untappd_url": "https://untappd.com/b/uchu-brewing-space-punch/6042400"
        }
    },
    # 3. 誤マッチ修正・未マッチ連携
    {
        "url": "https://151l.shop/?pid=193850879",
        "untappd_url": "https://untappd.com/b/firestone-walker-brewing-company-firestone-ipa/5597923",
        "gemini": {
            "beer_name_en": "Firestone IPA",
            "untappd_url": "https://untappd.com/b/firestone-walker-brewing-company-firestone-ipa/5597923"
        }
    },
    {
        "url": "https://beervolta.com/?pid=193865154",
        "untappd_url": "https://untappd.com/b/vatten-brewing-hell-boy/7182382",
        "gemini": {
            "untappd_url": "https://untappd.com/b/vatten-brewing-hell-boy/7182382"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001379",
        "untappd_url": "https://untappd.com/b/2nd-story-ale-works-dance/7139429",
        "gemini": {
            "untappd_url": "https://untappd.com/b/2nd-story-ale-works-dance/7139429"
        }
    },
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=8146",
        "untappd_url": None,
        "gemini": {
            "brewery_name_en": "amaku uku",
            "brewery_name_jp": "甘く浮く",
            "beer_name_en": "kasumi 2026",
            "beer_name_jp": "霞 2026"
        }
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    logger.info(f"Applying fixes for {len(FIXES)} items...")

    for item in FIXES:
        url = item["url"]
        untappd_url = item.get("untappd_url")
        gem_update = item.get("gemini")

        logger.info(f"\nProcessing: {url}")

        if gem_update:
            gem_res = sb.table("gemini_data").update(gem_update).eq("url", url).execute()
            logger.info(f"  [gemini_data] Updated: {len(gem_res.data)} rows")

        if untappd_url:
            sb_res = sb.table("scraped_beers").update({"untappd_url": untappd_url}).eq("url", url).execute()
            logger.info(f"  [scraped_beers] Updated untappd_url -> {untappd_url}")

            fail_res = sb.table("untappd_search_failures").update({
                "resolved": True,
                "resolved_at": now_iso,
                "notes": "Verified and resolved during inspection"
            }).eq("product_url", url).execute()
            if fail_res.data:
                logger.info(f"  [untappd_search_failures] Marked as resolved: {len(fail_res.data)} records")

            existing = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute().data
            if not existing:
                logger.info(f"  [untappd_data] Scraping details for {untappd_url}...")
                details = await scrape_beer_details(untappd_url)
                if details:
                    payload = map_details_to_payload(details)
                    payload["untappd_url"] = untappd_url
                    payload["fetched_at"] = now_iso
                    sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                    logger.info(f"  [untappd_data] Upserted: {payload.get('beer_name')}")
                else:
                    logger.warning(f"  [untappd_data] Failed to scrape {untappd_url}")
                await asyncio.sleep(2)
            else:
                logger.info(f"  [untappd_data] Already exists: {untappd_url}")

    logger.info("\nRefreshing materialized view (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("Materialized view refreshed successfully!")

if __name__ == '__main__':
    asyncio.run(main())

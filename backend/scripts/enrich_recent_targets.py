import asyncio
import logging
from datetime import datetime
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.commands.enrich_untappd import map_details_to_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TARGET_UPDATES = [
    {
        "url": "https://witchcraftmarket.com/products/shidenissen",
        "untappd_url": "https://untappd.com/b/isekado-ipa/55895",
        "gemini_update": {
            "brewery_name_en": "ISEKADO",
            "brewery_name_jp": "伊勢角屋麦酒",
            "untappd_url": "https://untappd.com/b/isekado-ipa/55895"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000000009",
        "untappd_url": "https://untappd.com/b/uchu-brewing-white-hole/2768357",
        "gemini_update": {
            "brewery_name_en": "UCHU BREWING",
            "brewery_name_jp": "うちゅうブルーイング",
            "untappd_url": "https://untappd.com/b/uchu-brewing-white-hole/2768357"
        }
    },
    {
        "url": "https://www.antenna-america.com/products/b055-c16005",
        "untappd_url": "https://untappd.com/b/revision-brewing-company-planet-lovetron/2419643",
        "gemini_update": {
            "brewery_name_en": "Revision Brewing Company",
            "brewery_name_jp": "リビジョン",
            "untappd_url": "https://untappd.com/b/revision-brewing-company-planet-lovetron/2419643"
        }
    },
    {
        "url": "https://maruho.shop/products/the-nomad-collab-w-societe-473ml-burgeon",
        "untappd_url": "https://untappd.com/b/burgeon-beer-company-the-nomad/6775461",
        "gemini_update": {
            "untappd_url": "https://untappd.com/b/burgeon-beer-company-the-nomad/6775461"
        }
    },
    {
        "url": "https://maruho.shop/products/カモノハシラガー-350ml-ひみつビール",
        "untappd_url": "https://untappd.com/b/himitsu-beer-platypus-lager/6836494",
        "gemini_update": {
            "beer_name_en": "Platypus Lager (カモノハシラガー)",
            "beer_name_core": "Platypus Lager",
            "untappd_url": "https://untappd.com/b/himitsu-beer-platypus-lager/6836494"
        }
    },
    {
        "url": "https://beervolta.com/?pid=193451257",
        "untappd_url": "https://untappd.com/b/nomcraft-brewing-dandy-crocodile/6894969",
        "gemini_update": {
            "untappd_url": "https://untappd.com/b/nomcraft-brewing-dandy-crocodile/6894969"
        }
    },
    {
        "url": "https://151l.shop/?pid=193292613",
        "untappd_url": "https://untappd.com/b/offshoot-beer-co-relax-it-s-just-our-anniversary/6631423",
        "gemini_update": {
            "untappd_url": "https://untappd.com/b/offshoot-beer-co-relax-it-s-just-our-anniversary/6631423"
        }
    },
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000001761",
        "untappd_url": "https://untappd.com/b/mangosteen-brewing-lab-asao-daikon/6595907",
        "gemini_update": {
            "beer_name_en": "Asao Daikon",
            "beer_name_core": "Asao Daikon",
            "untappd_url": "https://untappd.com/b/mangosteen-brewing-lab-asao-daikon/6595907"
        }
    }
]

async def main():
    sb = get_supabase_client()
    now_iso = datetime.utcnow().isoformat()

    logger.info(f"Starting enrichment for {len(TARGET_UPDATES)} target beers...")

    for item in TARGET_UPDATES:
        url = item["url"]
        untappd_url = item["untappd_url"]
        gem_update = item["gemini_update"]

        logger.info(f"\n==========================================")
        logger.info(f"Processing: {url}")
        logger.info(f"Target Untappd URL: {untappd_url}")

        # 1. Update gemini_data
        if gem_update:
            gem_res = sb.table("gemini_data").update(gem_update).eq("url", url).execute()
            logger.info(f"  [gemini_data] Updated: {len(gem_res.data)} rows")

        # 2. Update scraped_beers untappd_url
        sb_res = sb.table("scraped_beers").update({"untappd_url": untappd_url}).eq("url", url).execute()
        logger.info(f"  [scraped_beers] Updated untappd_url: {len(sb_res.data)} rows")

        # 3. Resolve failure history if any
        fail_res = sb.table("untappd_search_failures").update({
            "resolved": True,
            "resolved_at": now_iso,
            "notes": "Manually verified and resolved"
        }).eq("product_url", url).execute()
        if fail_res.data:
            logger.info(f"  [untappd_search_failures] Marked as resolved: {len(fail_res.data)} records")

        # 4. Ensure untappd_data has details
        existing_unt = sb.table("untappd_data").select("untappd_url").eq("untappd_url", untappd_url).execute().data
        if not existing_unt:
            logger.info(f"  [untappd_data] Scraping details for {untappd_url}...")
            details = await scrape_beer_details(untappd_url)
            if details:
                payload = map_details_to_payload(details)
                payload["untappd_url"] = untappd_url
                payload["fetched_at"] = now_iso
                ins_res = sb.table("untappd_data").upsert(payload, on_conflict="untappd_url").execute()
                logger.info(f"  [untappd_data] Upserted details: {ins_res.data}")
            else:
                logger.warning(f"  [untappd_data] Failed to scrape details for {untappd_url}")
            await asyncio.sleep(2)
        else:
            logger.info(f"  [untappd_data] Already exists: {untappd_url}")

    # 5. Refresh materialized view
    logger.info("\nRefreshing materialized view (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("Materialized view refreshed successfully!")

if __name__ == "__main__":
    asyncio.run(main())

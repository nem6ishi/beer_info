import asyncio
import logging
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.src.services.untappd.db_queries import upsert_untappd_data
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Target fixes: (shop_contains, name_contains, new_untappd_url)
FIXES = [
    {
        "shop": "マルホ酒店",
        "name_kw": "Series 55",
        "new_url": "https://untappd.com/b/evil-twin-brewing-nyc-the-great-side-project-blend-barrel-aged-series-55-released-02-13-26/6598079"
    },
    {
        "shop": "マルホ酒店",
        "name_kw": "Series 56",
        "new_url": "https://untappd.com/b/evil-twin-brewing-nyc-the-great-side-project-blend-barrel-aged-series-56-released-02-13-26/6598081"
    },
    {
        "shop": "一期一会～る",
        "name_kw": "ゼッドルプリン",
        "new_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-zed-lupulin/3483653"
    },
    {
        "shop": "アローム",
        "name_kw": "ゼッド・ルプリン",
        "new_url": "https://untappd.com/b/kcbc-kings-county-brewers-collective-zed-lupulin/3483653"
    },
    {
        "shop": "マルホ酒店",
        "name_kw": "Funky blender preserves apricot nectarine",
        "new_url": "https://untappd.com/b/casey-brewing-and-blending-funky-blender-preserves-apricot-nectarine/3906020"
    },
    {
        "shop": "ちょうせいや",
        "name_kw": "Barrel Aged Old Rasputin XXII",
        "new_url": "https://untappd.com/b/north-coast-brewing-company-rye-whiskey-barrel-aged-old-rasputin-xxii/3519128"
    },
    {
        "shop": "アローム",
        "name_kw": "バレルエイジド・オールドラスプーチン 22",
        "new_url": "https://untappd.com/b/north-coast-brewing-company-rye-whiskey-barrel-aged-old-rasputin-xxii/3519128"
    },
    {
        "shop": "アローム",
        "name_kw": "なまぺ",
        "new_url": "https://untappd.com/b/namachan-brewing/6596589"
    },
    {
        "shop": "アローム",
        "name_kw": "アメシスト 2024",
        "new_url": "https://untappd.com/b/bighand-bros-brewery-amethyst-2024/6536012"
    },
    {
        "shop": "BEER VOLTA",
        "name_kw": "スーパー クール キャット",
        "new_url": "https://untappd.com/b/nomcraft-brewing-super-cool-cat/6905516"
    },
    {
        "shop": "WITCH CRAFT MARKET",
        "name_kw": "[REVO BREWING] ONE",
        "new_url": "https://untappd.com/b/revo-brewing-one/4735057"
    }
]

async def main():
    supabase = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    unique_urls = list(set(f["new_url"] for f in FIXES))
    logger.info(f"Scraping {len(unique_urls)} Untappd URLs...")
    
    for url in unique_urls:
        logger.info(f"Scraping {url}...")
        details = await scrape_beer_details(url)
        if not details:
            logger.error(f"Failed to scrape {url}!")
            continue
        
        def parse_float(val):
            if val is None:
                return None
            try:
                return float(str(val).replace(",", "").replace("%", "").strip())
            except Exception:
                return None

        payload = {
            "untappd_url": url,
            "beer_name": details.get("untappd_beer_name"),
            "brewery_name": details.get("untappd_brewery_name"),
            "style": details.get("untappd_style"),
            "abv": details.get("untappd_abv"),
            "ibu": details.get("untappd_ibu"),
            "rating": str(details.get("untappd_rating")) if details.get("untappd_rating") is not None else None,
            "rating_count": str(details.get("untappd_rating_count")) if details.get("untappd_rating_count") is not None else None,
            "image_url": details.get("untappd_label"),
            "untappd_brewery_url": details.get("untappd_brewery_url"),
            "abv_num": parse_float(details.get("untappd_abv")),
            "ibu_num": parse_float(details.get("untappd_ibu")),
            "rating_num": parse_float(details.get("untappd_rating")),
            "rating_count_num": parse_float(details.get("untappd_rating_count")),
            "fetched_at": now_iso
        }
        upsert_untappd_data(supabase, [payload])
        logger.info(f"Upserted {payload['brewery_name']} - {payload['beer_name']} (rating: {payload['rating_num']})")

    # Update scraped_beers
    for f in FIXES:
        res = supabase.table("scraped_beers")\
            .select("url, name, shop")\
            .eq("shop", f["shop"])\
            .ilike("name", f"%{f['name_kw']}%")\
            .execute()
        
        for item in res.data:
            logger.info(f"Updating [{item['shop']}] {item['name']} -> {f['new_url']}")
            supabase.table("scraped_beers").update({
                "untappd_url": f["new_url"],
                "untappd_enriched_at": now_iso
            }).eq("url", item["url"]).execute()

    logger.info("Refreshing materialized view...")
    refresh_materialized_view(supabase, logger)
    logger.info("Successfully completed fix and refresh!")

if __name__ == "__main__":
    asyncio.run(main())

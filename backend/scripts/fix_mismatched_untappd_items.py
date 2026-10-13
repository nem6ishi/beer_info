"""
Fix mismatched Untappd items identified during inspection on 2026-10-13.
Applies correct Untappd URLs, fetches authentic details, and clears incorrect links.
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
    # 1. Modern Times Orderville (AA)
    {
        "url": "https://www.antenna-america.com/products/b067-c15989",
        "untappd_url": "https://untappd.com/b/modern-times-beer-orderville/467236",
        "gemini": {
            "brewery_name_en": "Modern Times Beer",
            "beer_name_en": "Orderville",
            "untappd_url": "https://untappd.com/b/modern-times-beer-orderville/467236"
        }
    },
    # 2. Modern Times Tropicolossal (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7402",
        "untappd_url": "https://untappd.com/b/modern-times-beer-tropicolossal/6634686",
        "gemini": {
            "brewery_name_en": "Modern Times Beer",
            "beer_name_en": "Tropicolossal",
            "untappd_url": "https://untappd.com/b/modern-times-beer-tropicolossal/6634686"
        }
    },
    # 3. Modern Times Tropicolossal (AA)
    {
        "url": "https://www.antenna-america.com/products/b067-c16053",
        "untappd_url": "https://untappd.com/b/modern-times-beer-tropicolossal/6634686",
        "gemini": {
            "brewery_name_en": "Modern Times Beer",
            "beer_name_en": "Tropicolossal",
            "untappd_url": "https://untappd.com/b/modern-times-beer-tropicolossal/6634686"
        }
    },
    # 4. Modern Times Parlay Lite Hazy IPA (AA) - Untappd未登録のためリンク解除
    {
        "url": "https://www.antenna-america.com/products/b067-c16052",
        "untappd_url": None,
        "gemini": {
            "brewery_name_en": "Modern Times Beer",
            "beer_name_en": "Parlay Lite Hazy IPA",
            "untappd_url": None
        }
    },
    # 5. Trap Door x Tiny Giants / Liminal Space (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7433",
        "untappd_url": "https://untappd.com/b/trap-door-brewing-liminal-space/6716611",
        "gemini": {
            "brewery_name_en": "Trap Door Brewing x Tiny Giants",
            "beer_name_en": "Liminal Space",
            "untappd_url": "https://untappd.com/b/trap-door-brewing-liminal-space/6716611"
        }
    },
    # 6. VERTERE / Rhoeas #33 (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7390",
        "untappd_url": "https://untappd.com/b/vertere-rhoeas/3336839",
        "gemini": {
            "brewery_name_en": "VERTERE",
            "beer_name_en": "Rhoeas",
            "untappd_url": "https://untappd.com/b/vertere-rhoeas/3336839"
        }
    },
    # 7. 渥美半島醸造×EVOLVE コズコズ (一期一会～る) - 未登録のため解除
    {
        "url": "https://151l.shop/?pid=193939045",
        "untappd_url": None,
        "gemini": {
            "brewery_name_en": "Atsumi Peninsula Brewing x EVOLVE",
            "beer_name_en": "KOZUKOZU",
            "beer_name_jp": "コズコズ",
            "untappd_url": None
        }
    },
    # 8. Coronado Crocodile Rock IPA (AA)
    {
        "url": "https://www.antenna-america.com/products/b015-c16007",
        "untappd_url": "https://untappd.com/b/coronado-brewing-company-crocodile-rock-citrus-ipa/6756641",
        "gemini": {
            "brewery_name_en": "Coronado Brewing Company",
            "beer_name_en": "Crocodile Rock Citrus IPA",
            "untappd_url": "https://untappd.com/b/coronado-brewing-company-crocodile-rock-citrus-ipa/6756641"
        }
    },
    # 9. Kestemont Oude Geuze (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6492",
        "untappd_url": "https://untappd.com/b/brouwerij-kestemont-oude-geuze/5483588",
        "gemini": {
            "brewery_name_en": "Brouwerij Kestemont",
            "beer_name_en": "Oude Geuze",
            "untappd_url": "https://untappd.com/b/brouwerij-kestemont-oude-geuze/5483588"
        }
    },
    # 10. Blade Factory × Mya Brew 猫の研ぎ職人 (一期一会～る) - 未登録のため解除
    {
        "url": "https://151l.shop/?pid=193188825",
        "untappd_url": None,
        "gemini": {
            "brewery_name_en": "Blade Factory Brewing x Mya Brew",
            "beer_name_en": "Neko no Togi Shokunin",
            "beer_name_jp": "猫の研ぎ職人",
            "untappd_url": None
        }
    },
    # 11. Jack's Abby House Helles Lager (AA)
    {
        "url": "https://www.antenna-america.com/products/b083-c15984",
        "untappd_url": "https://untappd.com/b/jack-s-abby-craft-lagers-house-lager/938789",
        "gemini": {
            "brewery_name_en": "Jack's Abby Craft Lagers",
            "beer_name_en": "House Lager",
            "untappd_url": "https://untappd.com/b/jack-s-abby-craft-lagers-house-lager/938789"
        }
    },
    # 12. AJB Co. Dry Hopped Foeder Saison (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7016",
        "untappd_url": "https://untappd.com/b/ajb-co-dry-hopped-foeder-saison/5239797",
        "gemini": {
            "brewery_name_en": "AJB Co.",
            "brewery_name_jp": "Anglo Japanese Brewing",
            "beer_name_en": "Dry Hopped Foeder Saison",
            "untappd_url": "https://untappd.com/b/ajb-co-dry-hopped-foeder-saison/5239797"
        }
    },
    # 13. AJB Co. Foeder Saison Vintage 2023 (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7015",
        "untappd_url": "https://untappd.com/b/ajb-co-foeder-saison/3464026",
        "gemini": {
            "brewery_name_en": "AJB Co.",
            "brewery_name_jp": "Anglo Japanese Brewing",
            "beer_name_en": "Foeder Saison Vintage 2023",
            "untappd_url": "https://untappd.com/b/ajb-co-foeder-saison/3464026"
        }
    },
    # 14. AJB Co. Foeder Sour Vintage 2024 (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7014",
        "untappd_url": "https://untappd.com/b/ajb-co-foeder-sour/3598915",
        "gemini": {
            "brewery_name_en": "AJB Co.",
            "brewery_name_jp": "Anglo Japanese Brewing",
            "beer_name_en": "Foeder Sour Vintage 2024",
            "untappd_url": "https://untappd.com/b/ajb-co-foeder-sour/3598915"
        }
    },
    # 15. AJB Co. Dry Hopped Brett Sour Vintage 2023 (750ml) (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6906",
        "untappd_url": "https://untappd.com/b/ajb-co-brett-sour/6287680",
        "gemini": {
            "brewery_name_en": "AJB Co.",
            "brewery_name_jp": "Anglo Japanese Brewing",
            "beer_name_en": "Dry Hopped Brett Sour Vintage 2023",
            "untappd_url": "https://untappd.com/b/ajb-co-brett-sour/6287680"
        }
    },
    # 16. AJB Co. Dry Hopped Brett Sour Vintage 2023 (375ml) (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6905",
        "untappd_url": "https://untappd.com/b/ajb-co-brett-sour/6287680",
        "gemini": {
            "brewery_name_en": "AJB Co.",
            "brewery_name_jp": "Anglo Japanese Brewing",
            "beer_name_en": "Dry Hopped Brett Sour Vintage 2023",
            "untappd_url": "https://untappd.com/b/ajb-co-brett-sour/6287680"
        }
    },
    # 17. Jever Pilsener (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6943",
        "untappd_url": "https://untappd.com/b/friesisches-brauhaus-zu-jever-jever-pilsener/5325",
        "gemini": {
            "brewery_name_en": "Friesisches Brauhaus zu Jever",
            "beer_name_en": "Jever Pilsener",
            "untappd_url": "https://untappd.com/b/friesisches-brauhaus-zu-jever-jever-pilsener/5325"
        }
    },
    # 18. North Coast Old Stock Ale Cellar Reserve 2018 (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6454",
        "untappd_url": "https://untappd.com/b/north-coast-brewing-company-old-stock-cellar-reserve-2018/3538435",
        "gemini": {
            "brewery_name_en": "North Coast Brewing Company",
            "beer_name_en": "Old Stock Ale Cellar Reserve 2018",
            "untappd_url": "https://untappd.com/b/north-coast-brewing-company-old-stock-cellar-reserve-2018/3538435"
        }
    },
    # 19. North Coast Barrel Aged Old Rasputin XXII (Rye) (アローム)
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=6912",
        "untappd_url": "https://untappd.com/b/north-coast-brewing-company-rye-whiskey-barrel-aged-old-rasputin-xxii/3519128",
        "gemini": {
            "brewery_name_en": "North Coast Brewing Company",
            "beer_name_en": "Barrel Aged Old Rasputin XXII (Rye)",
            "untappd_url": "https://untappd.com/b/north-coast-brewing-company-rye-whiskey-barrel-aged-old-rasputin-xxii/3519128"
        }
    },
    # 20. Offshoot Relax Anniversary DDH Hazy DIPA (AA)
    {
        "url": "https://www.antenna-america.com/products/b068-c16049",
        "untappd_url": "https://untappd.com/b/offshoot-beer-co-relax-it-s-just-our-anniversary/6631423",
        "gemini": {
            "brewery_name_en": "Offshoot Beer Co.",
            "beer_name_en": "Relax [it’s Just Our Anniversary]",
            "untappd_url": "https://untappd.com/b/offshoot-beer-co-relax-it-s-just-our-anniversary/6631423"
        }
    },
    # 21. Baa Baa Candy Baa Blueberry, Cranberry, Pistachio, Chocolate (一期一会～る)
    {
        "url": "https://151l.shop/?pid=193750035",
        "untappd_url": "https://untappd.com/b/baa-baa-brewhouse-candy-baa-blueberry-cranberry-chocolate-and-pistachio/4344191",
        "gemini": {
            "brewery_name_en": "Baa Baa Brewhouse",
            "beer_name_en": "Candy Baa - Blueberry, Cranberry, Chocolate & Pistachio",
            "untappd_url": "https://untappd.com/b/baa-baa-brewhouse-candy-baa-blueberry-cranberry-chocolate-and-pistachio/4344191"
        }
    },
    # 22. 箕面ビール 桃ヴァイツェン(川中島) (ちょうせいや)
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000003058",
        "untappd_url": "https://untappd.com/b/a-j-i-beer-inc-minoh-kokusan-momo-weizen-kawanakajima-hakutou-2022/5080470",
        "gemini": {
            "brewery_name_en": "Minoh Beer",
            "brewery_name_jp": "箕面ビール",
            "beer_name_en": "Kokusan Momo Weizen Kawanakajima Hakutou",
            "beer_name_jp": "国産桃ヴァイツェン 川中島白桃",
            "untappd_url": "https://untappd.com/b/a-j-i-beer-inc-minoh-kokusan-momo-weizen-kawanakajima-hakutou-2022/5080470"
        }
    },
    # 23. RIKRI : Encore (BeerVolta)
    {
        "url": "https://beervolta.com/?pid=193073582",
        "untappd_url": "https://untappd.com/b/rikri-brewing-encore/6831280",
        "gemini": {
            "brewery_name_en": "RIKRI BREWING",
            "brewery_name_jp": "リクリブルーイング",
            "beer_name_en": "Encore",
            "beer_name_jp": "アンコール",
            "untappd_url": "https://untappd.com/b/rikri-brewing-encore/6831280"
        }
    },
    # 24. Kure's Craft Beverage Strawberry Vodka Lemonade (AA) - RTDカクテルのため解除
    {
        "url": "https://www.antenna-america.com/products/b134-c16008",
        "untappd_url": None,
        "gemini": {
            "brewery_name_en": "Kure's Craft Beverage",
            "beer_name_en": "Strawberry Vodka Lemonade",
            "product_type": "other",
            "untappd_url": None
        }
    },
    # 25. 宇宙ZOMBIE (ちょうせいや) - ブルワリー抽出修正
    {
        "url": "https://beer-chouseiya.shop/shopdetail/000000002004",
        "untappd_url": "https://untappd.com/b/uchu-brewing-zombie-uchu-zombie/6960941",
        "gemini": {
            "brewery_name_en": "Uchu Brewing",
            "brewery_name_jp": "うちゅうブルーイング",
            "beer_name_en": "UCHU ZOMBIE",
            "beer_name_jp": "宇宙ZOMBIE",
            "untappd_url": "https://untappd.com/b/uchu-brewing-zombie-uchu-zombie/6960941"
        }
    },
    # 26. GMT+9 / Paradise Planet (アローム) - ブルワリー抽出修正
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7820",
        "untappd_url": "https://untappd.com/b/west-coast-brewing-gmt-9-paradise-planet/6808064",
        "gemini": {
            "brewery_name_en": "West Coast Brewing",
            "beer_name_en": "GMT+9 / Paradise Planet",
            "untappd_url": "https://untappd.com/b/west-coast-brewing-gmt-9-paradise-planet/6808064"
        }
    },
    # 27. Pomona Island / PAFNUTE (アローム) - ブルワリー抽出修正
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7089",
        "untappd_url": "https://untappd.com/b/pomona-island-brew-co-pafnute/5844425",
        "gemini": {
            "brewery_name_en": "Pomona Island Brew Co.",
            "beer_name_en": "PAFNUTE",
            "untappd_url": "https://untappd.com/b/pomona-island-brew-co-pafnute/5844425"
        }
    },
    # 28. Pomona Island / Tamaki IV (アローム) - ブルワリー抽出修正
    {
        "url": "https://www.arome.jp/products/detail.php?product_id=7650",
        "untappd_url": "https://untappd.com/b/pomona-island-brew-co-tamaki-iv/6321139",
        "gemini": {
            "brewery_name_en": "Pomona Island Brew Co.",
            "beer_name_en": "TAMAKI IV",
            "untappd_url": "https://untappd.com/b/pomona-island-brew-co-tamaki-iv/6321139"
        }
    },
    # 29. Cloudwater / Race Your Own Heart (一期一会～る) - ブルワリー抽出修正
    {
        "url": "https://151l.shop/?pid=185806654",
        "untappd_url": "https://untappd.com/b/cloudwater-brew-co-race-your-own-heart/5010156",
        "gemini": {
            "brewery_name_en": "Cloudwater Brew Co.",
            "beer_name_en": "Race Your Own Heart",
            "untappd_url": "https://untappd.com/b/cloudwater-brew-co-race-your-own-heart/5010156"
        }
    }
]

async def apply_fixes():
    supabase = get_supabase_client()
    logger.info(f"Starting to apply {len(FIXES)} fixes...")

    # Cache scraped Untappd details so identical URLs don't scrape twice
    untappd_details_cache = {}

    for fix in FIXES:
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
            else:
                logger.warning(f"  ⚠️ Could not scrape full details for {u_url}, linking URL directly.")

            # Update scraped_beers
            supabase.table('scraped_beers').update({'untappd_url': u_url}).eq('url', p_url).execute()
            logger.info(f"  ✅ Updated scraped_beers with untappd_url: {u_url}")
        else:
            # Clear Untappd URL
            supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', p_url).execute()
            logger.info(f"  ✅ Cleared untappd_url in scraped_beers for {p_url}")

        if gemini:
            # Check if gemini record exists
            chk = supabase.table('gemini_data').select('url').eq('url', p_url).execute()
            gemini_payload = {**gemini, 'url': p_url}
            if chk.data:
                supabase.table('gemini_data').update(gemini_payload).eq('url', p_url).execute()
                logger.info(f"  ✅ Updated gemini_data: {gemini_payload}")
            else:
                supabase.table('gemini_data').insert(gemini_payload).execute()
                logger.info(f"  ✅ Inserted gemini_data: {gemini_payload}")

    # Refresh materialized view
    refresh_materialized_view(supabase, logger)
    logger.info("🎉 All fixes applied and view refreshed successfully!")

if __name__ == '__main__':
    asyncio.run(apply_fixes())

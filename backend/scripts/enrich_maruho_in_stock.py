import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.store.brewery_manager import BreweryManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def enrich_maruho():
    sb = get_supabase_client()
    bm = BreweryManager()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("📦 Enriching Maruho In-Stock Beers (Rule-based + Dictionary)")
    logger.info("=" * 70)

    # 1. Fetch in-stock items from Maruho
    res = sb.table('scraped_beers').select('url, name, first_seen').eq('shop', 'マルホ酒店').eq('stock_status', 'In Stock').execute()
    in_stock_items = res.data or []
    logger.info(f"Total in-stock Maruho items: {len(in_stock_items)}")

    # 2. Get existing gemini_data urls
    existing_urls = set()
    offset = 0
    while True:
        r = sb.table('gemini_data').select('url').range(offset, offset + 999).execute()
        rows = r.data or []
        if not rows:
            break
        for row in rows:
            existing_urls.add(row['url'])
        offset += 1000
        if len(rows) < 1000:
            break

    targets = [b for b in in_stock_items if b['url'] not in existing_urls]
    logger.info(f"Target unextracted Maruho items: {len(targets)}")

    payloads = []
    for item in targets:
        url = item['url']
        name = item['name']

        # Check for set / gift / glass / goods
        is_set = False
        ptype = 'beer'
        if any(w in name for w in ['セット', 'ギフトボックス', '6本セット', '3本セット', 'お任せセット']):
            is_set = True
            ptype = 'set'
        elif any(w in name for w in ['グラス', 'グラウラー', 'パイントグラス', 'タンブラー', 'DrinkTanks']):
            ptype = 'glass'
        elif any(w in name for w in ['Tシャツ', 'コースター', 'ステッカー', 'キーホルダー', 'キャップ']):
            ptype = 'other'

        beer_name_en = None
        beer_name_jp = None
        brewery_name_en = None
        brewery_name_jp = None

        if '/' in name:
            parts = name.rsplit('/', 1)
            raw_beer = parts[0].strip()
            raw_brewery = parts[1].strip()

            # Clean beer name (strip volume like 330ml, 750ml, and dates like 2026-07)
            clean_beer = re.sub(r'\b\d{3,4}ml\b', '', raw_beer, flags=re.IGNORECASE)
            clean_beer = re.sub(r'\b20\d{2}-\d{2}\b', '', clean_beer)
            clean_beer = re.sub(r'[\(\[（].*?[\)\]）]', '', clean_beer)
            clean_beer = ' '.join(clean_beer.split()).strip()

            # Clean brewery
            clean_brewery = re.sub(r'[\(\[（].*?[\)\]）]', '', raw_brewery).strip()

            # Find brewery in BreweryManager
            found = bm.find_breweries_in_text(clean_brewery)
            if found:
                brewery_name_en = found[0]['name_en']
                brewery_name_jp = found[0].get('name_jp') or clean_brewery
            else:
                brewery_name_en = clean_brewery
                brewery_name_jp = clean_brewery

            # Determine whether raw_beer is EN or JP
            has_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', raw_beer))
            if has_japanese:
                beer_name_jp = clean_beer
                beer_name_en = clean_beer  # fallback
            else:
                beer_name_en = clean_beer
                beer_name_jp = None
        else:
            # No slash, e.g. "馨和KAGUA‐Rouge‐"
            clean_name = re.sub(r'\b\d{3,4}ml\b', '', name, flags=re.IGNORECASE).strip()
            found = bm.find_breweries_in_text(clean_name)
            if found:
                brewery_name_en = found[0]['name_en']
                brewery_name_jp = found[0].get('name_jp')
            beer_name_en = clean_name

        payload = {
            'url': url,
            'brewery_name_en': brewery_name_en,
            'brewery_name_jp': brewery_name_jp,
            'beer_name_en': beer_name_en,
            'beer_name_jp': beer_name_jp,
            'beer_name_core': beer_name_en,
            'search_hint': f"{beer_name_en or ''} {brewery_name_en or ''}".strip(),
            'product_type': ptype,
            'is_set': is_set,
            'payload': {
                'raw_name': name,
                'extracted_by': 'rule_maruho',
                'brewery_en': brewery_name_en,
                'beer_en': beer_name_en,
            },
            'updated_at': now_iso,
        }
        payloads.append(payload)

    logger.info(f"Generated {len(payloads)} payloads. Saving in batches of 50...")
    for i in range(0, len(payloads), 50):
        chunk = payloads[i:i+50]
        sb.table('gemini_data').upsert(chunk, on_conflict='url').execute()
        logger.info(f"  💾 Saved batch {i//50 + 1}/{(len(payloads)-1)//50 + 1} ({len(chunk)} items)")

    logger.info("🔄 Refreshing beer_info_view...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ Maruho enrichment complete!")

if __name__ == "__main__":
    asyncio.run(enrich_maruho())

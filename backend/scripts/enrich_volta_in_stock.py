import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.store.brewery_manager import BreweryManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def enrich_volta():
    sb = get_supabase_client()
    bm = BreweryManager()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("📦 Enriching BEER VOLTA In-Stock Beers (Rule-based + Dictionary)")
    logger.info("=" * 70)

    # 1. Fetch in-stock items from BEER VOLTA
    res = sb.table('scraped_beers').select('url, name, first_seen').eq('shop', 'BEER VOLTA').eq('stock_status', 'In Stock').execute()
    in_stock_items = res.data or []
    logger.info(f"Total in-stock BEER VOLTA items: {len(in_stock_items)}")

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
    logger.info(f"Target unextracted BEER VOLTA items: {len(targets)}")

    payloads = []
    for item in targets:
        url = item['url']
        name = item['name']

        is_set = False
        ptype = 'beer'
        if any(w in name for w in ['セット', 'ギフトボックス', '6本セット', '3本セット', 'Mix Pack']):
            is_set = True
            ptype = 'set'
        elif any(w in name for w in ['グラス', 'グラウラー', 'パイントグラス', 'タンブラー']):
            ptype = 'glass'
        elif any(w in name for w in ['Tシャツ', 'コースター', 'ステッカー', 'キーホルダー', 'キャップ']):
            ptype = 'other'

        raw_jp = ""
        raw_en = name

        if '/' in name:
            parts = name.split('/', 1)
            raw_jp = parts[0].strip()
            raw_en = parts[1].strip()
        elif '|' in name:
            parts = name.split('|', 1)
            raw_jp = parts[0].strip()
            raw_en = parts[1].strip()

        # Clean volume & packaging
        clean_en = re.sub(r'\b\d{3,4}ml\b', '', raw_en, flags=re.IGNORECASE).strip()
        clean_en = re.sub(r'[\(\[（].*?[\)\]）]', '', clean_en).strip()
        clean_en = ' '.join(clean_en.split())

        # Match brewery in EN or JP
        found = bm.find_breweries_in_text(clean_en) or bm.find_breweries_in_text(raw_en)
        if not found and raw_jp:
            found = bm.find_breweries_in_text(raw_jp)

        brewery_name_en = None
        brewery_name_jp = None
        beer_name_en = None

        if found:
            b_info = found[0]
            brewery_name_en = b_info['name_en']
            brewery_name_jp = b_info.get('name_jp')
            
            # Remove brewery name/alias from clean_en to get beer name
            matched_names = [brewery_name_en]
            if brewery_name_jp:
                matched_names.append(brewery_name_jp)
            if b_info.get('aliases'):
                matched_names.extend(b_info['aliases'])

            # Try to strip matched brewery
            beer_candidate = clean_en
            for m in matched_names:
                pattern = re.compile(re.escape(m), re.IGNORECASE)
                if pattern.search(beer_candidate):
                    beer_candidate = pattern.sub('', beer_candidate).strip()
                    break
            
            # Clean up leading punctuation like ':' or '-'
            beer_candidate = re.sub(r'^[\s:\-–—]+', '', beer_candidate).strip()
            beer_name_en = beer_candidate or clean_en
        else:
            # Fallback heuristic: if "Brewery : Beer" or "Brewery - Beer"
            if ':' in clean_en:
                b_part, beer_part = clean_en.split(':', 1)
                brewery_name_en = b_part.strip()
                beer_name_en = beer_part.strip()
            elif '-' in clean_en:
                b_part, beer_part = clean_en.split('-', 1)
                brewery_name_en = b_part.strip()
                beer_name_en = beer_part.strip()
            else:
                words = clean_en.split()
                if len(words) >= 2:
                    brewery_name_en = words[0]
                    beer_name_en = ' '.join(words[1:])
                else:
                    brewery_name_en = clean_en
                    beer_name_en = clean_en

        payload = {
            'url': url,
            'brewery_name_en': brewery_name_en,
            'brewery_name_jp': brewery_name_jp,
            'beer_name_en': beer_name_en,
            'beer_name_jp': raw_jp if raw_jp else None,
            'beer_name_core': beer_name_en,
            'search_hint': f"{beer_name_en or ''} {brewery_name_en or ''}".strip(),
            'product_type': ptype,
            'is_set': is_set,
            'payload': {
                'raw_name': name,
                'extracted_by': 'rule_volta',
                'brewery_en': brewery_name_en,
                'beer_en': beer_name_en,
            },
            'updated_at': now_iso,
        }
        payloads.append(payload)

    logger.info(f"Generated {len(payloads)} payloads for BEER VOLTA. Saving in batches of 50...")
    for i in range(0, len(payloads), 50):
        chunk = payloads[i:i+50]
        sb.table('gemini_data').upsert(chunk, on_conflict='url').execute()
        logger.info(f"  💾 Saved batch {i//50 + 1}/{(len(payloads)-1)//50 + 1} ({len(chunk)} items)")

    logger.info("🔄 Refreshing beer_info_view...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ BEER VOLTA enrichment complete!")

if __name__ == "__main__":
    asyncio.run(enrich_volta())

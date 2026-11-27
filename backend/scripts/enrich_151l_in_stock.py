import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.store.brewery_manager import BreweryManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def enrich_151l():
    sb = get_supabase_client()
    bm = BreweryManager()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 70)
    logger.info("📦 Enriching 一期一会～る In-Stock Beers (Rule-based + Dictionary)")
    logger.info("=" * 70)

    # 1. Fetch in-stock items from 151l
    res = sb.table('scraped_beers').select('url, name, first_seen').eq('shop', '一期一会～る').eq('stock_status', 'In Stock').execute()
    in_stock_items = res.data or []
    logger.info(f"Total in-stock 151l items: {len(in_stock_items)}")

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
    logger.info(f"Target unextracted 151l items: {len(targets)}")

    payloads = []
    for item in targets:
        url = item['url']
        name = item['name']

        is_set = False
        ptype = 'beer'
        if any(w in name for w in ['セット', 'お任せセット', 'コース', 'コース品', 'ギフトボックス', '飲み比べ']):
            is_set = True
            ptype = 'set'
        elif any(w in name for w in ['グラス', 'パイントグラス', 'テイスティンググラス', 'オリジナルグラス']):
            ptype = 'glass'
        elif any(w in name for w in ['Tシャツ', 'コースター', 'ステッカー', 'グッズ', 'キャップ', '書籍', '本']):
            ptype = 'other'

        # Look for parenthesized English name: e.g. （Fort George Magnetic Fields） or (Burley Oak J.R.E.A.M.)
        m = re.findall(r'[\(（]([^\)）]+)[\)）]', name)
        
        brewery_name_en = None
        brewery_name_jp = None
        beer_name_en = None
        beer_name_jp = None

        if m:
            # Usually the last parens contain the English name
            eng_candidate = m[-1].strip()
            # If parens contain mostly English words
            if re.search(r'[a-zA-Z]{3,}', eng_candidate):
                clean_en = re.sub(r'\b\d{3,4}ml\b', '', eng_candidate, flags=re.IGNORECASE).strip()
                clean_en = re.sub(r'\bCAN\b', '', clean_en, flags=re.IGNORECASE).strip()
                clean_en = ' '.join(clean_en.split())

                # Find brewery
                found = bm.find_breweries_in_text(clean_en)
                if not found:
                    # Try Japanese part before parens, removing promotional brackets like 【...】
                    jp_part = re.sub(r'【.*?】|\[.*?\]', '', name).strip()
                    jp_part = re.sub(r'[\(（].*?[\)）]', '', jp_part).strip()
                    found = bm.find_breweries_in_text(jp_part)

                if found:
                    b_info = found[0]
                    brewery_name_en = b_info['name_en']
                    brewery_name_jp = b_info.get('name_jp')
                    
                    matched_names = [brewery_name_en]
                    if brewery_name_jp:
                        matched_names.append(brewery_name_jp)
                    if b_info.get('aliases'):
                        matched_names.extend(b_info['aliases'])

                    beer_candidate = clean_en
                    for mn in matched_names:
                        pattern = re.compile(re.escape(mn), re.IGNORECASE)
                        if pattern.search(beer_candidate):
                            beer_candidate = pattern.sub('', beer_candidate).strip()
                            break
                    beer_name_en = re.sub(r'^[\s:\-–—]+', '', beer_candidate).strip() or clean_en
                else:
                    words = clean_en.split()
                    if len(words) >= 2:
                        brewery_name_en = words[0]
                        beer_name_en = ' '.join(words[1:])
                    else:
                        brewery_name_en = clean_en
                        beer_name_en = clean_en
        
        if not brewery_name_en:
            # Fallback to Japanese title parsing
            jp_title = re.sub(r'【.*?】', '', name).strip()
            jp_title = re.sub(r'[\(（].*?[\)）]', '', jp_title).strip()
            found = bm.find_breweries_in_text(jp_title)
            if found:
                brewery_name_en = found[0]['name_en']
                brewery_name_jp = found[0].get('name_jp')
            beer_name_en = jp_title

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
                'extracted_by': 'rule_151l',
                'brewery_en': brewery_name_en,
                'beer_en': beer_name_en,
            },
            'updated_at': now_iso,
        }
        payloads.append(payload)

    logger.info(f"Generated {len(payloads)} payloads for 一期一会～る. Saving in batches of 50...")
    for i in range(0, len(payloads), 50):
        chunk = payloads[i:i+50]
        sb.table('gemini_data').upsert(chunk, on_conflict='url').execute()
        logger.info(f"  💾 Saved batch {i//50 + 1}/{(len(payloads)-1)//50 + 1} ({len(chunk)} items)")

    logger.info("🔄 Refreshing beer_info_view...")
    refresh_materialized_view(sb, logger)
    logger.info("✅ 一期一会～る enrichment complete!")

if __name__ == "__main__":
    asyncio.run(enrich_151l())

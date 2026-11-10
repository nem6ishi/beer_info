"""
Manual Untappd enrichment script for in-stock beers.
Runs rule-based extraction for missing gemini_data,
then performs rate-limited Untappd searches (skip_llm=True).
"""
import asyncio
import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple, Set

from src.core.db import get_supabase_client, refresh_materialized_view
from src.core.utils import map_details_to_payload
from src.services.store.brewery_manager import BreweryManager
from src.services.untappd.searcher import get_untappd_url, scrape_beer_details
from src.services.untappd.db_queries import upsert_untappd_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Non-beer indicators
GLASS_INDICATORS = ["グラス", "glass", "タンブラー", "tumbler", "パイント", "pint"]
GOODS_INDICATORS = [
    "tシャツ", "t-shirt", "ステッカー", "sticker", "キーホルダー", "コースター", 
    "バッグ", "bag", "キャップ", "帽子", "クージー", "koozie", "グラウラー", "growler",
    "ポスター", "poster", "graphic art", "額入り", "缶バッジ"
]
SET_INDICATORS = [
    "ギフトボックス", "3本セット", "4本セット", "6本セット", "8本セット", "12本セット", 
    "お任せセット", "飲み比べセット", "beer pass", "mix pack", "mixpack", "variety pack"
]
CIDER_INDICATORS = ["サイダー", "cider", "シードル", "cidre"]
MEAD_INDICATORS = ["ミード", "mead", "蜂蜜酒"]

def parse_product_info(name: str, shop: str, brewery_manager: BreweryManager) -> Dict[str, Any]:
    """Rule-based extractor for product_type, brewery_name, and beer_name."""
    name_lower = name.lower()

    # 1. Product type classification
    if any(k in name_lower for k in GLASS_INDICATORS):
        return {"product_type": "glass", "brewery_name_en": None, "beer_name_en": name}
    if any(k in name_lower for k in GOODS_INDICATORS):
        return {"product_type": "other", "brewery_name_en": None, "beer_name_en": name}
    if any(k in name_lower for k in SET_INDICATORS) or "セット" in name or "mixpack" in name_lower:
        return {"product_type": "set", "brewery_name_en": None, "beer_name_en": name}
    if any(k in name_lower for k in CIDER_INDICATORS):
        return {"product_type": "cider", "brewery_name_en": None, "beer_name_en": name}
    if any(k in name_lower for k in MEAD_INDICATORS):
        return {"product_type": "mead", "brewery_name_en": None, "beer_name_en": name}

    brewery_en: Optional[str] = None
    beer_en: Optional[str] = None

    # Pattern 0: BEER VOLTA pipe pattern (JP : JP | EN_Brewery: EN_Beer)
    if '|' in name:
        parts = name.split('|')
        en_part = parts[-1].strip()
        if ':' in en_part or '：' in en_part:
            b_cand, beer_cand = re.split(r'[:：]', en_part, 1)
            b_cand = b_cand.strip()
            beer_cand = beer_cand.strip()
            b_match = brewery_manager.find_brewery_in_text(b_cand)
            brewery_en = b_match.get('name_en') if b_match else b_cand
            beer_en = re.sub(r'【.*?】|\[.*?\]|\(.*?\)|（.*?）|\d+ml', '', beer_cand).strip()
            return {"product_type": "beer", "brewery_name_en": brewery_en, "beer_name_en": beer_en}

    # Pattern A: [Brewery] Beer / Japanese
    m_bracket = re.match(r'^\[(.*?)\]\s*(.*)$', name)
    if m_bracket:
        brewery_part = m_bracket.group(1).strip()
        rest = m_bracket.group(2).strip()
        b_match = brewery_manager.find_brewery_in_text(brewery_part)
        brewery_en = b_match.get('name_en') if b_match else brewery_part
        # Remove japanese suffix after slash if present
        beer_en = rest.split('/')[0].strip()
        beer_en = re.sub(r'（.*?）|\(.*?\)|【.*?】', '', beer_en).strip()
        return {"product_type": "beer", "brewery_name_en": brewery_en, "beer_name_en": beer_en}

    # Check known brewery hints first
    brewery_obj = brewery_manager.find_brewery_in_text(name)
    if brewery_obj and brewery_obj.get("name_en"):
        brewery_en = brewery_obj["name_en"]

    # Pattern B: Japanese / English (BEER VOLTA / Arome style: '... / Brewery Beer' or '... / Brewery: Beer')
    if '/' in name:
        parts = [p.strip() for p in name.split('/')]
        en_part = parts[-1]
        en_part = re.sub(r'【.*?】|\[.*?\]|\(.*?\)|（.*?）|\d+ml|\d+oz', '', en_part).strip()

        if ':' in en_part or '：' in en_part:
            b_cand, beer_cand = re.split(r'[:：]', en_part, 1)
            if not brewery_en:
                b_match = brewery_manager.find_brewery_in_text(b_cand.strip())
                brewery_en = b_match.get('name_en') if b_match else b_cand.strip()
            beer_en = beer_cand.strip()
        else:
            # Check if en_part contains brewery
            b_match = brewery_manager.find_brewery_in_text(en_part)
            if b_match:
                if not brewery_en:
                    brewery_en = b_match.get('name_en')
                beer_cand = en_part
                for alias in [b_match.get('name_en'), b_match.get('name_jp')] + (b_match.get('aliases') or []):
                    if alias and alias.lower() in beer_cand.lower():
                        pattern = re.compile(re.escape(alias), re.IGNORECASE)
                        beer_cand = pattern.sub('', beer_cand).strip()
                beer_en = beer_cand.strip(' -:/')
            elif brewery_en:
                beer_en = re.sub(re.escape(brewery_en), '', en_part, flags=re.IGNORECASE).strip(' -:/')
            else:
                tokens = en_part.split()
                if len(tokens) >= 2:
                    cand_m = brewery_manager.find_brewery_in_text(' '.join(tokens[:2])) or brewery_manager.find_brewery_in_text(tokens[0])
                    if cand_m:
                        brewery_en = cand_m.get('name_en')
                        beer_en = re.sub(re.escape(cand_m.get('name_en')), '', en_part, flags=re.IGNORECASE).strip(' -:/')
                    else:
                        brewery_en = tokens[0]
                        beer_en = ' '.join(tokens[1:]).strip(' -:/')

    # Pattern C: Chouseiya style '【Beer/Brewery】'
    m_chouseiya = re.search(r'【(.*?)/(.*?)】', name)
    if m_chouseiya:
        beer_cand = m_chouseiya.group(1).strip()
        brewery_cand = m_chouseiya.group(2).strip()
        # Clean (賞味期限/...) or other metadata from brewery_cand
        brewery_cand = re.sub(r'[\(（].*?[\)）]', '', brewery_cand).strip()
        if not brewery_en or brewery_cand.lower() == 'うちゅう':
            b_match = brewery_manager.find_brewery_in_text(brewery_cand)
            brewery_en = b_match.get('name_en') if b_match else brewery_cand
        beer_en = beer_cand

    # Pattern D: Colon without pipe (Brewery : Beer)
    if not beer_en and (':' in name or '：' in name):
        b_cand, beer_cand = re.split(r'[:：]', name, 1)
        b_match = brewery_manager.find_brewery_in_text(b_cand.strip())
        if b_match:
            brewery_en = b_match.get('name_en')
            beer_en = beer_cand.strip()

    if not beer_en:
        cleaned = re.sub(r'【.*?】|\[.*?\]|\(.*?\)|（.*?）|\d+ml|\d+本', '', name).strip()
        if brewery_en:
            cleaned = re.sub(re.escape(brewery_en), '', cleaned, flags=re.IGNORECASE).strip()
        beer_en = cleaned.split('/')[0].strip(' -:/')

    return {
        "product_type": "beer",
        "brewery_name_en": brewery_en,
        "beer_name_en": beer_en
    }

async def process_untappd_item(
    sem: asyncio.Semaphore,
    supabase: Any,
    item: Dict[str, Any],
    brewery_en: str,
    beer_en: str,
    stats: Dict[str, int]
):
    url = item['url']
    raw_name = item.get('name', '')

    async with sem:
        try:
            logger.info(f"🔍 Searching: '{brewery_en}' - '{beer_en}' ({raw_name[:35]})")
            result = await get_untappd_url(
                brewery_name=brewery_en,
                beer_name=beer_en,
                original_title=raw_name,
                skip_llm=True
            )

            now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

            if result.get('success') and result.get('url'):
                untappd_url = result['url']
                details = result.get('details') or {}
                logger.info(f"  ✅ MATCHED: {untappd_url} ({details.get('beer_name', 'Unknown')})")

                # 1. Upsert untappd_data
                if details:
                    payload = map_details_to_payload(details)
                    payload['untappd_url'] = untappd_url
                    payload['url'] = untappd_url
                    try:
                        upsert_untappd_data(supabase, payload)
                    except Exception as e:
                        logger.warning(f"Error upserting untappd_data: {e}")

                # 2. Update scraped_beers
                supabase.table('scraped_beers').update({
                    'untappd_url': untappd_url,
                    'untappd_enriched_at': now_iso
                }).eq('url', url).execute()

                stats['matched'] += 1
            else:
                logger.info(f"  ❌ No Untappd match for: {brewery_en} - {beer_en}")
                supabase.table('scraped_beers').update({
                    'untappd_enriched_at': now_iso
                }).eq('url', url).execute()
                stats['not_found'] += 1

        except Exception as e:
            logger.error(f"Error searching {url}: {e}")
            stats['error'] += 1

        await asyncio.sleep(0.5)  # Be polite to Untappd

async def main():
    supabase = get_supabase_client()
    brewery_manager = BreweryManager()

    logger.info("=" * 60)
    logger.info("🍺 Starting Manual Untappd Enrichment for In-Stock Beers")
    logger.info("=" * 60)

    # 1. Fetch In-Stock items without untappd_url
    res = supabase.table('scraped_beers').select('url, name, shop')\
        .eq('stock_status', 'In Stock')\
        .is_('untappd_url', 'null')\
        .execute()
    items = res.data or []
    logger.info(f"Found {len(items)} in-stock items without untappd_url.")

    if not items:
        logger.info("All in-stock items already have Untappd URLs!")
        return

    # 2. Check existing gemini_data in chunks
    urls = [b['url'] for b in items]
    gemini_map: Dict[str, Dict[str, Any]] = {}

    def chunked(it, n):
        for i in range(0, len(it), n):
            yield it[i:i + n]

    for b_urls in chunked(urls, 50):
        g_res = supabase.table('gemini_data').select('*').in_('url', b_urls).execute()
        for r in (g_res.data or []):
            gemini_map[r['url']] = r

    # 3. Create or re-parse gemini_data entries via enhanced rule-based parser
    updated_gemini_payloads = []
    for b in items:
        url = b['url']
        existing = gemini_map.get(url)
        parsed = parse_product_info(b['name'], b.get('shop', ''), brewery_manager)
        needs_update = False
        if not existing:
            needs_update = True
        elif parsed['product_type'] in ('glass', 'other', 'set', 'cider', 'mead') and existing.get('product_type') not in ('glass', 'other', 'set', 'cider', 'mead'):
            needs_update = True
        elif not existing.get('brewery_name_en') and parsed.get('brewery_name_en'):
            needs_update = True
        elif not existing.get('beer_name_en') and parsed.get('beer_name_en'):
            needs_update = True

        if needs_update:
            payload = {
                "url": url,
                "brewery_name_en": parsed["brewery_name_en"] or (existing.get("brewery_name_en") if existing else None),
                "beer_name_en": parsed["beer_name_en"] or (existing.get("beer_name_en") if existing else None),
                "product_type": parsed["product_type"],
                "is_set": parsed["product_type"] == "set",
                "created_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            updated_gemini_payloads.append(payload)
            gemini_map[url] = {**(existing or {}), **payload}

    if updated_gemini_payloads:
        for batch in chunked(updated_gemini_payloads, 50):
            try:
                supabase.table('gemini_data').upsert(batch, on_conflict='url').execute()
            except Exception as e:
                logger.error(f"Error upserting rule-based gemini_data: {e}")
        logger.info(f"Saved {len(updated_gemini_payloads)} rule-based gemini_data records.")

    # 4. Filter beer items for Untappd search
    beer_items = []
    non_beer_count = 0
    for b in items:
        g = gemini_map.get(b['url'], {})
        p_type = g.get('product_type', 'beer')
        if p_type in ('glass', 'other', 'set', 'cider', 'mead'):
            non_beer_count += 1
            # Mark enriched so it doesn't stay pending
            supabase.table('scraped_beers').update({
                'untappd_enriched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }).eq('url', b['url']).execute()
            continue
        beer_items.append((b, g.get('brewery_name_en') or '', g.get('beer_name_en') or ''))

    logger.info(f"Target beers for Untappd search: {len(beer_items)} (Non-beer goods/sets/glasses filtered: {non_beer_count})")

    # 5. Search Untappd concurrently (concurrency=4)
    sem = asyncio.Semaphore(4)
    stats = {'matched': 0, 'not_found': 0, 'error': 0}

    tasks = [
        process_untappd_item(sem, supabase, b, br, be, stats)
        for b, br, be in beer_items
    ]

    await asyncio.gather(*tasks)

    # 6. Refresh view
    logger.info("=" * 60)
    logger.info("⚡ Refreshing beer_info_view materialized view...")
    refresh_materialized_view(supabase, logger)

    logger.info("=" * 60)
    logger.info(f"🎉 Untappd Enrichment Finished!")
    logger.info(f"  - Matched & Linked: {stats['matched']}")
    logger.info(f"  - Not Found on Untappd: {stats['not_found']}")
    logger.info(f"  - Non-beer (glass/set/goods): {non_beer_count}")
    logger.info(f"  - Errors: {stats['error']}")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

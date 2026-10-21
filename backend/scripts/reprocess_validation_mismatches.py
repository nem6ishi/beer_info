"""
Reprocess beers that failed with 'final_validation_mismatch'.
Prioritizes currently in-stock items, applies improved validation rules,
and links matched Untappd URLs to the database.
"""
import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Add workspace root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.src.core.db import get_supabase_client
from backend.src.core.logging import setup_logging
from backend.src.commands.enrich_untappd import UntappdEnricher
from backend.src.commands.failure_tracker import resolve_search_failure

logger = setup_logging("reprocess_mismatches")


async def main():
    parser = argparse.ArgumentParser(description="Reprocess final_validation_mismatch beers")
    parser.add_argument("--limit", type=int, default=50, help="Max items to process")
    parser.add_argument("--in-stock-only", action="store_true", help="Only process items currently in stock")
    parser.add_argument("--force", action="store_true", help="Force link even if validation is marginal")
    args = parser.parse_args()

    supabase = get_supabase_client()

    logger.info("🔍 Fetching unresolved final_validation_mismatch records...")
    all_failures = []
    page = 0
    limit = 1000
    while True:
        res = supabase.table('untappd_search_failures') \
            .select('product_url, failure_reason, beer_name, brewery_name, last_failed_at, last_error_message') \
            .eq('resolved', False) \
            .eq('failure_reason', 'final_validation_mismatch') \
            .range(page * limit, (page + 1) * limit - 1) \
            .execute()
        all_failures.extend(res.data or [])
        if len(res.data or []) < limit:
            break
        page += 1

    logger.info(f"Total unresolved final_validation_mismatch: {len(all_failures)}")
    if not all_failures:
        logger.info("No mismatches found to process.")
        return

    # Fetch corresponding scraped_beers and gemini_data
    urls = [f['product_url'] for f in all_failures]
    scraped_map = {}
    gemini_map = {}

    for i in range(0, len(urls), 200):
        chunk = urls[i:i+200]
        sb_res = supabase.table('scraped_beers').select(
            'url, name, shop, stock_status, untappd_url'
        ).in_('url', chunk).execute()
        for r in (sb_res.data or []):
            scraped_map[r['url']] = r

        g_res = supabase.table('gemini_data').select(
            'url, beer_name_en, beer_name_jp, brewery_name_en, brewery_name_jp, product_type, untappd_url'
        ).in_('url', chunk).execute()
        for r in (g_res.data or []):
            gemini_map[r['url']] = r

    # Combine into candidate objects
    candidates: List[Dict[str, Any]] = []
    for f in all_failures:
        p_url = f['product_url']
        sb = scraped_map.get(p_url)
        if not sb:
            continue
        g = gemini_map.get(p_url, {})
        candidate = {
            'url': p_url,
            'name': sb.get('name', ''),
            'shop': sb.get('shop', ''),
            'stock_status': sb.get('stock_status', 'Unknown'),
            'beer_name_en': g.get('beer_name_en') or f.get('beer_name'),
            'beer_name_jp': g.get('beer_name_jp'),
            'brewery_name_en': g.get('brewery_name_en') or f.get('brewery_name'),
            'brewery_name_jp': g.get('brewery_name_jp'),
            'product_type': g.get('product_type', 'beer'),
            'untappd_url': sb.get('untappd_url') or g.get('untappd_url'),
            'last_failed_at': f.get('last_failed_at'),
            'last_error_message': f.get('last_error_message', ''),
        }
        if args.in_stock_only and candidate['stock_status'] != 'In Stock':
            continue
        candidates.append(candidate)

    # Sort candidates: 'In Stock' first, then latest last_failed_at descending
    def sort_key(c):
        in_stock_score = 0 if c['stock_status'] == 'In Stock' else 1
        failed_at = c.get('last_failed_at') or ''
        return (in_stock_score, -len(failed_at), failed_at)

    candidates.sort(key=lambda c: (0 if c['stock_status'] == 'In Stock' else 1, c.get('last_failed_at') or ''), reverse=False)
    # Sort In Stock first, then newer failed_at first
    in_stock_list = [c for c in candidates if c['stock_status'] == 'In Stock']
    in_stock_list.sort(key=lambda c: c.get('last_failed_at') or '', reverse=True)
    other_list = [c for c in candidates if c['stock_status'] != 'In Stock']
    other_list.sort(key=lambda c: c.get('last_failed_at') or '', reverse=True)
    sorted_candidates = (in_stock_list + other_list)[:args.limit]

    logger.info(f"Targeting {len(sorted_candidates)} items ({len([c for c in sorted_candidates if c['stock_status'] == 'In Stock'])} In Stock)")

    enricher = UntappdEnricher(mode='missing', force=args.force)

    success_count = 0
    failure_count = 0

    for idx, item in enumerate(sorted_candidates, 1):
        url = item['url']
        name = item['name']
        shop = item['shop']
        status = item['stock_status']
        logger.info(f"\n--- [{idx}/{len(sorted_candidates)}] [{shop} | {status}] {name} ---")

        try:
            # Sleep 2s between requests to be gentle on Untappd search/scrape
            await asyncio.sleep(2)
            result = await enricher._process_beer_missing(item)

            if result and (result.get('untappd_url') or result.get('untappd_payload')):
                u_url = result.get('untappd_url') or result.get('untappd_payload', {}).get('untappd_url')
                logger.info(f"  🎉 Successfully resolved & linked: {u_url}")
                
                # Commit updates immediately
                payload = result.get('untappd_payload')
                if payload:
                    try:
                        supabase.table('untappd_data').upsert([payload]).execute()
                    except Exception as e_ud:
                        logger.warning(f"  ⚠️ Could not upsert untappd_data: {e_ud}")

                # Update scraped_beers
                now_iso = datetime.now(timezone.utc).isoformat()
                supabase.table('scraped_beers').update({
                    'untappd_url': u_url,
                    'untappd_enriched_at': now_iso
                }).eq('url', url).execute()

                # Update gemini_data
                try:
                    supabase.table('gemini_data').update({'untappd_url': u_url}).eq('url', url).execute()
                except Exception:
                    pass

                # Resolve failure record
                resolve_search_failure(supabase, url)
                success_count += 1
            else:
                logger.warning(f"  ❌ Still failed to match/link.")
                failure_count += 1

        except Exception as e:
            logger.error(f"  💥 Exception processing {name}: {e}", exc_info=True)
            failure_count += 1

    logger.info("\n" + "=" * 50)
    logger.info(f"Reprocessing completed:")
    logger.info(f"  - Successfully linked: {success_count}")
    logger.info(f"  - Still failed / skipped: {failure_count}")
    logger.info("=" * 50)


if __name__ == '__main__':
    asyncio.run(main())

"""
Script to manually enrich in-stock beers that are missing untappd_url:
1. LLM extraction for missing gemini_data
2. Untappd search & details linking
"""
import asyncio
import logging
from typing import List, Dict, Any, Set

from src.core.db import get_supabase_client, refresh_materialized_view
from src.commands.enrich_extract import LLMEnricher
from src.commands.enrich_untappd import UntappdEnricher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def chunked(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i:i + n]

async def run_enrichment():
    supabase = get_supabase_client()

    # 1. Fetch In Stock items missing untappd_url
    logger.info("Fetching in-stock beers without untappd_url...")
    res = supabase.table('scraped_beers').select('url, name, shop, first_seen')\
        .eq('stock_status', 'In Stock')\
        .is_('untappd_url', 'null')\
        .execute()
    items = res.data or []
    logger.info(f"Found {len(items)} in-stock items without untappd_url.")

    if not items:
        logger.info("No items to enrich.")
        return

    urls = [b['url'] for b in items]

    # Check gemini_data in chunks
    existing_gemini_urls: Set[str] = set()
    for batch_urls in chunked(urls, 50):
        g_res = supabase.table('gemini_data').select('url').in_('url', batch_urls).execute()
        for r in (g_res.data or []):
            existing_gemini_urls.add(r['url'])

    missing_gemini_items = [b for b in items if b['url'] not in existing_gemini_urls]
    logger.info(f"Items missing gemini_data: {len(missing_gemini_items)}")

    # Phase 1: LLM Extraction
    if missing_gemini_items:
        logger.info("=" * 60)
        logger.info(f"🤖 Phase 1: LLM Extraction for {len(missing_gemini_items)} items...")
        enricher = LLMEnricher(llm_provider='gemini')
        for i, beer in enumerate(missing_gemini_items):
            logger.info(f"[{i+1}/{len(missing_gemini_items)}] {beer.get('shop')}: {beer.get('name', '')[:40]}")
            try:
                status, payload = await enricher._process_item(beer)
                if payload:
                    enricher.pending_payloads.append(payload)
                    if len(enricher.pending_payloads) >= 10:
                        enricher._save_gemini_data_batch(enricher.pending_payloads)
                        enricher.pending_payloads.clear()
            except Exception as e:
                logger.error(f"Error extracting {beer.get('url')}: {e}")

        if enricher.pending_payloads:
            enricher._save_gemini_data_batch(enricher.pending_payloads)
            enricher.pending_payloads.clear()

        logger.info("Phase 1 LLM Extraction complete.")

    # Phase 2: Untappd Search
    logger.info("=" * 60)
    logger.info("🍺 Phase 2: Untappd Search for all in-stock unlinked items...")

    # We will reset untappd_enriched_at to null for these in-stock items so UntappdEnricher picks them up
    logger.info("Clearing untappd_enriched_at for in-stock candidates to ensure retry...")
    for batch_urls in chunked(urls, 50):
        try:
            supabase.table('scraped_beers').update({'untappd_enriched_at': None}).in_('url', batch_urls).execute()
        except Exception as e:
            logger.warning(f"Error resetting untappd_enriched_at: {e}")

    # Also clear search failures for these items so backoff doesn't block them
    for batch_urls in chunked(urls, 50):
        try:
            supabase.table('untappd_search_failures').delete().in_('product_url', batch_urls).execute()
        except Exception as e:
            logger.warning(f"Error clearing search failures: {e}")

    untappd_enricher = UntappdEnricher(mode='missing', force=True)
    # Process up to len(items) + 20
    await untappd_enricher.run(limit=len(items) + 20)

    # Phase 3: Refresh view
    logger.info("=" * 60)
    logger.info("⚡ Refreshing beer_info_view...")
    refresh_materialized_view(supabase, logger)

    # Phase 4: Final tally
    res_after = supabase.table('scraped_beers').select('url', count='exact')\
        .eq('stock_status', 'In Stock')\
        .is_('untappd_url', 'null')\
        .execute()
    logger.info(f"🎉 Enrichment done! Remaining in-stock without untappd_url: {res_after.count} (was {len(items)})")

if __name__ == "__main__":
    asyncio.run(run_enrichment())

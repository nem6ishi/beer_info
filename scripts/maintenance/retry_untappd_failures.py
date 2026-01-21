#!/usr/bin/env python3
"""
Retry Untappd search failures.
Re-runs enrichment for failed searches, optionally filtered by reason.
"""
import sys
import asyncio
import argparse
import logging
from app.core.db import get_supabase_client
from app.commands.enrich_untappd import process_beer_missing

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def retry_failures(reason_filter=None, limit=10):
    """
    Retry failed Untappd searches.
    
    Args:
        reason_filter: Optional failure reason to filter by
        limit: Maximum number of failures to retry
    """
    supabase = get_supabase_client()
    
    # Build query to get unresolved failures
    query = supabase.table('untappd_search_failures') \
        .select('product_url, brewery_name, beer_name, beer_name_jp, failure_reason, search_attempts') \
        .eq('resolved', False)
    
    if reason_filter:
        query = query.eq('failure_reason', reason_filter)
    
    # Order by attempts (fewer first) then by last_failed_at (oldest first)
    response = query.order('search_attempts').order('first_failed_at').limit(limit).execute()
    failures = response.data
    
    if not failures:
        logger.info("✨ リトライする失敗ケースはありません")
        return 0
    
    logger.info(f"📋 {len(failures)}件の失敗ケースをリトライします")
    if reason_filter:
        logger.info(f"フィルタ: failure_reason = {reason_filter}")
    
    success_count = 0
    still_failed_count = 0
    
    for i, failure in enumerate(failures, 1):
        product_url = failure['product_url']
        brewery = failure.get('brewery_name')
        beer_name = failure.get('beer_name')
        beer_name_jp = failure.get('beer_name_jp')
        
        logger.info(f"\n{'='*70}")
        logger.info(f"[{i}/{len(failures)}] Retrying: {brewery} - {beer_name}")
        logger.info(f"Previous failure reason: {failure['failure_reason']}")
        logger.info(f"Previous attempts: {failure['search_attempts']}")
        logger.info(f"{'='*70}")
        
        # Get full beer data from beer_info_view
        beer_response = supabase.table('beer_info_view') \
            .select('*') \
            .eq('url', product_url) \
            .maybe_single() \
            .execute()
        
        if not beer_response.data:
            logger.warning(f"⚠️  Product not found in beer_info_view: {product_url}")
            continue
        
        beer = beer_response.data
        
        # Attempt to enrich
        try:
            result = await process_beer_missing(beer, offline=False)
            
            if result:
                success_count += 1
                logger.info(f"✅ SUCCESS: Linked to Untappd!")
            else:
                still_failed_count += 1
                logger.info(f"❌ STILL FAILED: Could not find Untappd link")
        except Exception as e:
            still_failed_count += 1
            logger.error(f"❌ ERROR during retry: {e}")
        
        # Rate limiting
        await asyncio.sleep(2)
    
    # Summary
    logger.info(f"\n{'='*70}")
    logger.info("📊 RETRY SUMMARY")
    logger.info(f"{'='*70}")
    logger.info(f"Total attempted: {len(failures)}")
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Still failed: {still_failed_count}")
    logger.info(f"{'='*70}\n")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description='Retry failed Untappd searches')
    parser.add_argument('--reason', 
                       help='Only retry failures with this reason',
                       choices=['missing_info', 'no_results', 'network_error', 'validation_failed'])
    parser.add_argument('--limit', 
                       type=int, 
                       default=10,
                       help='Maximum number of failures to retry (default: 10)')
    
    args = parser.parse_args()
    
    # Run async function
    return asyncio.run(retry_failures(
        reason_filter=args.reason,
        limit=args.limit
    ))


if __name__ == "__main__":
    sys.exit(main())

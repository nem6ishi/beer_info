"""
Scan existing beer data for variant modifier mismatches between
the expected beer name (beer_name_en) and the Untappd beer name (untappd_beer_name).
Beers with mismatches have their untappd_url cleared for re-enrichment.
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.core.db import get_supabase_client
from backend.src.services.untappd.text_utils import has_variant_mismatch

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def scan_and_report():
    """
    Scans beer_info_view for variant modifier mismatches.
    Returns list of mismatched records.
    """
    supabase = get_supabase_client()
    
    # Fetch all beers that have both beer_name_en and untappd data
    logger.info("📂 Fetching beers with Untappd URLs from beer_info_view...")
    
    all_mismatches = []
    offset = 0
    batch_size = 500
    
    while True:
        res = supabase.table('beer_info_view') \
            .select('url, name, beer_name_en, beer_name_jp, untappd_url, untappd_beer_name, brewery_name_en') \
            .not_.is_('untappd_url', 'null') \
            .not_.is_('untappd_beer_name', 'null') \
            .not_.is_('beer_name_en', 'null') \
            .limit(batch_size) \
            .offset(offset) \
            .execute()
        
        beers = res.data or []
        if not beers:
            break
        
        for beer in beers:
            beer_name_en = beer.get('beer_name_en', '')
            untappd_beer_name = beer.get('untappd_beer_name', '')
            
            if not beer_name_en or not untappd_beer_name:
                continue
            
            # Check for variant modifier mismatch
            if has_variant_mismatch(beer_name_en, untappd_beer_name):
                all_mismatches.append({
                    'url': beer.get('url'),
                    'name': beer.get('name', ''),
                    'beer_name_en': beer_name_en,
                    'untappd_beer_name': untappd_beer_name,
                    'untappd_url': beer.get('untappd_url'),
                    'brewery_name_en': beer.get('brewery_name_en', ''),
                })
        
        offset += batch_size
        logger.info(f"  Processed {offset} records...")

    return all_mismatches


def clear_mismatched_urls(mismatches):
    """
    Clears untappd_url for mismatched beers so they can be re-enriched.
    Updates both scraped_beers and gemini_data tables.
    """
    supabase = get_supabase_client()
    cleared = 0
    
    for m in mismatches:
        url = m['url']
        if not url:
            continue
        
        try:
            # Clear untappd_url in scraped_beers
            supabase.table('scraped_beers').update({
                'untappd_url': None
            }).eq('url', url).execute()
            
            # Clear untappd_url in gemini_data
            supabase.table('gemini_data').update({
                'untappd_url': None
            }).eq('url', url).execute()
            
            cleared += 1
            logger.info(f"  🗑️  Cleared: {m['beer_name_en']} (was → {m['untappd_beer_name']})")
        except Exception as e:
            logger.error(f"  ❌ Error clearing {url}: {e}")
    
    return cleared


def main():
    mismatches = scan_and_report()
    
    logger.info(f"\n{'='*70}")
    logger.info(f"🔍 Found {len(mismatches)} variant modifier mismatches")
    logger.info(f"{'='*70}\n")
    
    if not mismatches:
        logger.info("✨ No mismatches found!")
        return
    
    # Display all mismatches
    for i, m in enumerate(mismatches, 1):
        logger.info(f"  [{i}] {m['brewery_name_en']} - {m['beer_name_en']}")
        logger.info(f"      → Untappd: {m['untappd_beer_name']}")
        logger.info(f"      → URL: {m['untappd_url']}")
        logger.info("")
    
    # Ask for confirmation
    answer = input(f"\n🗑️  Clear untappd_url for these {len(mismatches)} beers? (y/N): ").strip().lower()
    if answer == 'y':
        cleared = clear_mismatched_urls(mismatches)
        logger.info(f"\n✅ Cleared {cleared}/{len(mismatches)} URLs. Run enrich_untappd to re-enrich.")
    else:
        logger.info("⏭️  Skipped. No changes made.")


if __name__ == '__main__':
    main()

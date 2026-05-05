import logging
from typing import List, Dict, Any

from ..core.db import get_supabase_client
from ..services.untappd.text_utils import has_variant_mismatch

logger = logging.getLogger(__name__)

async def scan_and_report() -> List[Dict[str, Any]]:
    """
    Scans beer_info_view for variant modifier mismatches.
    Returns list of mismatched records.
    """
    supabase = get_supabase_client()
    
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

async def clear_mismatched_urls(mismatches: List[Dict[str, Any]]) -> int:
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

async def check_variants(auto_clear: bool = False) -> None:
    """
    Main command function to check for variant mismatches.
    """
    mismatches = await scan_and_report()
    
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
    
    if auto_clear:
        cleared = await clear_mismatched_urls(mismatches)
        logger.info(f"\n✅ Auto-cleared {cleared}/{len(mismatches)} URLs. Run enrich-untappd to re-enrich.")
    else:
        logger.info("\n💡 Run with --clear flag to automatically clear these untappd_urls.")

import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.utils.script_utils import setup_script

def reset_yexit():
    supabase, logger = setup_script("ResetYEXIT")
    
    target_url = "https://beer-chouseiya.shop/shopdetail/000000002527"
    bad_untappd = "https://untappd.com/search?q=YEXIT%20%E3%83%A8%E3%83%AD%E3%83%83%E3%82%B3"
    
    logger.info(f"Resetting Untappd URL for: {target_url}")
    
    # 1. Clear from gemini_data
    supabase.table('gemini_data').update({'untappd_url': None}).eq('url', target_url).execute()
    logger.info("Cleared gemini_data")
    
    # 2. Clear from scraped_beers (if column exists and is used)
    # Checking if scraped_beers has untappd_url... assuming yes based on previous logs
    try:
        supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', target_url).execute()
        logger.info("Cleared scraped_beers")
    except Exception as e:
        logger.warning(f"Could not clear scraped_beers (might not exist): {e}")

    # 3. Delete the bad untappd_data row
    try:
        supabase.table('untappd_data').delete().eq('untappd_url', bad_untappd).execute()
        logger.info(f"Deleted bad untappd_data row: {bad_untappd}")
    except Exception as e:
        logger.warning(f"Error deleting untappd_data: {e}")

if __name__ == "__main__":
    reset_yexit()

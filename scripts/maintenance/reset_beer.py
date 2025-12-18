import os
import sys
import argparse

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.utils.script_utils import setup_script

def reset_beer(target_url):
    supabase, logger = setup_script("ResetBeer")
    
    logger.info(f"Resetting Untappd URL for: {target_url}")
    
    # 1. Clear from gemini_data
    supabase.table('gemini_data').update({'untappd_url': None}).eq('url', target_url).execute()
    logger.info("Cleared gemini_data")
    
    # 2. Clear from scraped_beers
    try:
        supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', target_url).execute()
        logger.info("Cleared scraped_beers")
    except Exception as e:
        logger.warning(f"Could not clear scraped_beers: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('url', type=str, help='Product URL to reset')
    args = parser.parse_args()
    reset_beer(args.url)

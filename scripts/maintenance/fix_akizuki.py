import os
import sys
import asyncio

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.utils.script_utils import setup_script
from scripts.maintenance.manual_link import manual_link

async def fix_akizuki():
    supabase, logger = setup_script("FixAkizuki")
    
    target_url = "https://beer-chouseiya.shop/shopdetail/000000002216"
    untappd_url = "https://untappd.com/b/yorocco-beer-dry-hopped-farmhouse-ale/5119963"
    
    # 1. Fix Gemini Data
    logger.info("Fixing Gemini Data (Far Yeast -> Yorocco Beer)...")
    supabase.table('gemini_data').update({'brewery_name_en': 'Yorocco Beer'}).eq('url', target_url).execute()
    
    # 2. Manual Link
    await manual_link(target_url, untappd_url)

if __name__ == "__main__":
    asyncio.run(fix_akizuki())

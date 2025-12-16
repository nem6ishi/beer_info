
import asyncio
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from app.services.untappd_searcher import scrape_beer_details
from scripts.enrich_untappd import map_details_to_payload

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

async def fix_namachan():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Target Product
    target_product_url = "https://beer-chouseiya.shop/shopdetail/000000000914/all_items/page1/order/"
    
    # Correct Untappd Link
    correct_url = "https://untappd.com/b/namachan-brewing-nama-s-cat-can/6522773"
    
    print(f"Fixing Product: {target_product_url}")
    print(f"Correct Untappd: {correct_url}")
    
    # 1. Scrape correct details
    print("Scraping details from correct URL...")
    details = scrape_beer_details(correct_url)
    if not details:
        print("❌ Failed to scrape details from correct URL.")
        return
        
    print(f"✅ Details scraped: {details.get('untappd_beer_name')} ({details.get('untappd_rating')})")
    
    # 2. Prepare payload
    untappd_payload = map_details_to_payload(details)
    untappd_payload['untappd_url'] = correct_url
    
    # 3. Upsert to untappd_data
    try:
        supabase.table('untappd_data').upsert(untappd_payload).execute()
        print("✅ Saved to untappd_data.")
    except Exception as e:
        print(f"❌ Error saving to untappd_data: {e}")
        return

    # 4. Persistence & Link
    try:
        # Update gemini_data
        supabase.table('gemini_data').update({'untappd_url': correct_url}).eq('url', target_product_url).execute()
        
        # Update scraped_beers
        supabase.table('scraped_beers').update({'untappd_url': correct_url}).eq('url', target_product_url).execute()
        print("✅ Updated linkages.")
        
    except Exception as e:
        print(f"❌ Error updating links: {e}")
        
    print("✨ Fix completed!")

if __name__ == "__main__":
    asyncio.run(fix_namachan())

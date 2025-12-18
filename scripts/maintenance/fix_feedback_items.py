import asyncio
import os
from datetime import datetime, timezone
from supabase import create_client
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.services.untappd_searcher import scrape_beer_details

load_dotenv()
url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

async def fix_items():
    # 1. Fix Messorem (6737) - Unset "is_set"
    messorem_url = "https://www.arome.jp/products/detail.php?product_id=6737"
    print(f"🔧 Correcting Messorem set status for {messorem_url}...")
    supabase.table("gemini_data").update({"is_set": False}).eq("url", messorem_url).execute()
    print("✅ Messorem fixed in gemini_data.")

    # 2. Fix Vertere (6736) - Scrape details
    vertere_untappd_url = "https://untappd.com/b/vertere-emoryi/6043841"
    print(f"🔄 Fetching details for Vertere: {vertere_untappd_url}...")
    details = scrape_beer_details(vertere_untappd_url)
    if details:
        payload = {
            'untappd_url': vertere_untappd_url,
            'beer_name': details.get('untappd_beer_name'),
            'brewery_name': details.get('untappd_brewery_name'),
            'style': details.get('untappd_style'),
            'abv': details.get('untappd_abv'),
            'ibu': details.get('untappd_ibu'),
            'rating': details.get('untappd_rating'),
            'rating_count': details.get('untappd_rating_count'),
            'image_url': details.get('untappd_label'),
            'untappd_brewery_url': details.get('untappd_brewery_url'),
            'fetched_at': datetime.now(timezone.utc).isoformat()
        }
        supabase.table("untappd_data").upsert(payload).execute()
        print(f"✅ Vertere details updated: Rating {details.get('untappd_rating')}")
    else:
        print("❌ Failed to scrape Vertere details.")

if __name__ == "__main__":
    asyncio.run(fix_items())


import os
import sys
from supabase import create_client
from dotenv import load_dotenv
import asyncio

# Add app to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.untappd_searcher import scrape_beer_details, UntappdBeerDetails

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def get_supabase_client():
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    return create_client(supabase_url, supabase_key)

def map_details_to_payload(details: UntappdBeerDetails):
    from datetime import datetime, timezone
    return {
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': details.get('untappd_brewery_name'),
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'ibu': details.get('untappd_ibu'),
        'rating': details.get('untappd_rating'),
        'rating_count': details.get('untappd_rating_count'),
        'image_url': details.get('untappd_label'),
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }

def manual_enrich_and_update():
    supabase = get_supabase_client()
    
    updates = [
        {
            "name_fragment": "フランボワーズ",
            "url": "https://untappd.com/b/wakasaimo-honpo-oni-densetsu-framboise/118413"
        },
        {
            "name_fragment": "シシリアンルージュ",
            "url": "https://untappd.com/b/wakasaimo-honpo-oni-densetsu-sicilian-rouge/154539"
        }
    ]
    
    print("Robust manual update for Oni Densetsu items...")
    
    for update in updates:
        print(f"Processing: {update['name_fragment']}")
        
        # 1. Scrape details first
        print(f"  Scraping details from {update['url']}...")
        details = scrape_beer_details(update['url'])
        
        payload = {}
        if details:
            payload = map_details_to_payload(details)
            print(f"  Scraped: {payload.get('beer_name')} ({payload.get('rating')})")
        else:
            print("  Failed to scrape details. Using minimal payload.")
            
        payload['untappd_url'] = update['url']
        
        # 2. Upsert into untappd_data (overwrite any existing data for this URL)
        print(f"  Upserting to untappd_data...")
        supabase.table('untappd_data').upsert(payload).execute()
        
        # 3. Find target items in scraped_beers
        res = supabase.table('scraped_beers').select('url, name').ilike('name', f'%{update["name_fragment"]}%').ilike('name', '%鬼伝説%').execute()
        
        if not res.data:
            print("  No items found in scanned_beers to link.")
            continue
            
        for item in res.data:
            print(f"  Linking: {item['name']}")
            # Update scraped_beers
            supabase.table('scraped_beers').update({'untappd_url': update['url']}).eq('url', item['url']).execute()
            # Update gemini_data
            supabase.table('gemini_data').update({'untappd_url': update['url']}).eq('url', item['url']).execute()

    print("Complete.")

if __name__ == "__main__":
    manual_enrich_and_update()

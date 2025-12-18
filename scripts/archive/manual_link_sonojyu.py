
import asyncio
import os
import sys
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import scrape_beer_details, UntappdBeerDetails
from scripts.utils.script_utils import setup_script
from scripts.enrich_untappd import map_details_to_payload

# Setup
supabase, logger = setup_script("manual_link_sonojyu")

async def manual_link():
    target_url = "https://untappd.com/b/tamamura-honten-co-shiga-kogen-sono-10-no-10-anniversary-ipa/850141"
    target_name_keyword = "%SHIGA KOGEN BEER SONO JYU%"
    
    print(f"🔗 Manually linking Sono Jyu to: {target_url}")

    # 1. Scrape details from the correct URL
    print("  🔄 Scraping details from Untappd...")
    details = scrape_beer_details(target_url)
    if not details:
        print("  ❌ Failed to scrape details. Aborting.")
        return

    print(f"  ✅ Scraped: {details.get('untappd_beer_name')} ({details.get('untappd_rating')})")
    
    # 2. Prepare Payload
    untappd_payload = map_details_to_payload(details)
    untappd_payload['untappd_url'] = target_url # Ensure PK
    
    # 3. Save to untappd_data
    try:
        supabase.table('untappd_data').upsert(untappd_payload).execute()
        print("  💾 Saved to untappd_data")
    except Exception as e:
        print(f"  ❌ Error saving untappd_data: {e}")
        return

    # 4. Find the Gemini item to update
    res = supabase.table('beer_info_view').select('*').ilike('name', target_name_keyword).execute()
    beers = res.data
    
    if not beers:
        print("  ❌ No matching beer found in DB.")
        return
        
    for beer in beers:
        print(f"  Updating: {beer['name']}")
        
        # 5. Update gemini_data (URL AND Name Correction)
        # Verify if the current English extraction is confusing or wrong
        # "SONO JYU" is correct japanglish but Untappd uses "Sono 10"
        updates = {
            'untappd_url': target_url,
            'beer_name_en': "Sono 10 / No. 10 (Anniversary IPA)", 
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if beer.get('url'):
            try:
                supabase.table('gemini_data').update(updates).eq('url', beer['url']).execute()
                print("  💾 Updated gemini_data (URL + Name)")
            except Exception as e:
                print(f"  ❌ Error updating gemini_data: {e}")

            # 6. Update scraped_beers link
            try:
                supabase.table('scraped_beers').update({'untappd_url': target_url}).eq('url', beer['url']).execute()
                print("  🔗 Updated scraped_beers link")
            except Exception as e:
                print(f"  ❌ Error updating scraped_beers: {e}")

if __name__ == "__main__":
    asyncio.run(manual_link())

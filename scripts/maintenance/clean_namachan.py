
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def clean_namachan():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    target_name = 'ナマチャン やみつきエール ブラックペッパー / NAMACHAN American IPA w/Black Paper'
    print(f"Cleaning Gemini data for: {target_name}")
    
    # First get the URL to identify the record uniquely
    res = supabase.table('scraped_beers').select('url').eq('name', target_name).execute()
    
    if not res.data:
        print("Target beer not found in scraped_beers.")
        return

    url = res.data[0]['url']
    print(f"Target URL: {url}")
    
    # Delete from gemini_data
    # This will cause enrich_gemini to pick it up again as a 'missing' item
    try:
        supabase.table('gemini_data').delete().eq('url', url).execute()
        print("✅ Deleted from gemini_data.")
    except Exception as e:
        print(f"❌ Error deleting gemini_data: {e}")

    # Also clear untappd_url from scraped_beers to ensure full re-linking
    try:
        supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', url).execute()
        print("✅ Cleared untappd_url in scraped_beers.")
    except Exception as e:
        print(f"❌ Error updating scraped_beers: {e}")
        
    # Also delete from untappd_data if we want to force re-search? 
    # Actually, untappd_data is keyed by untappd_url. 
    # If the previous link was WRONG (Black Tide search result), we should probably let it simple link to new one.
    # The previous untappd_url was a search link. It's fine to leave it in untappd_data table as a record, 
    # but we broke the link in scraped_beers so it's effectively gone for this beer.

if __name__ == "__main__":
    clean_namachan()

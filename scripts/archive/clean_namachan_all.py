
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def clean_namachan_all():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    keyword = "NAMACHA"
    print(f"Searching for items containing '{keyword}'...")
    
    # Supabase ilike
    res = supabase.table('scraped_beers').select('url, name').ilike('name', f'%{keyword}%').execute()
    
    items = res.data
    if not items:
        print("No items found.")
        return
        
    print(f"Found {len(items)} items.")
    
    urls = [item['url'] for item in items]
    
    # Delete from gemini_data
    print(f"Deleting {len(urls)} records from gemini_data...")
    try:
        # Delete in chunks if too many, but small number ok
        if len(urls) > 0:
            supabase.table('gemini_data').delete().in_('url', urls).execute()
        print("✅ Deleted from gemini_data.")
    except Exception as e:
        print(f"❌ Error deleting gemini_data: {e}")

    # Clear untappd_url in scraped_beers
    print("Clearing untappd_url in scraped_beers...")
    try:
        if len(urls) > 0:
             supabase.table('scraped_beers').update({'untappd_url': None}).in_('url', urls).execute()
        print("✅ Cleared untappd_url in scraped_beers.")
    except Exception as e:
        print(f"❌ Error updating scraped_beers: {e}")

if __name__ == "__main__":
    clean_namachan_all()

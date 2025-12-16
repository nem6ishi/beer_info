
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def get_supabase_client():
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    return create_client(supabase_url, supabase_key)

def manual_link():
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
    
    print("Manual linking for Oni Densetsu items...")
    
    for update in updates:
        print(f"Searching for items containing: {update['name_fragment']}")
        
        # Find items
        res = supabase.table('scraped_beers').select('url, name').ilike('name', f'%{update["name_fragment"]}%').ilike('name', '%鬼伝説%').execute()
        
        if not res.data:
            print("  No items found.")
            continue
            
        for item in res.data:
            print(f"  Linking: {item['name']} -> {update['url']}")
            
            # Update scraped_beers
            supabase.table('scraped_beers').update({'untappd_url': update['url']}).eq('url', item['url']).execute()
            
            # Update gemini_data (persistence)
            supabase.table('gemini_data').update({'untappd_url': update['url']}).eq('url', item['url']).execute()
            
            # Ensure untappd_data entry exists (might not scrape details immediately, but link is saved)
            # Use enrich_untappd logic or simple insert logic if needed? 
            # For now just linking. Ideally we should trigger a scrape for these details too.
            
            # Upsert into untappd_data to ensure foreign key validity if we had FKs (we don't strictly enforce yet but good practice)
            # We'll just insert a placeholder if it doesn't exist so the link works
            check = supabase.table('untappd_data').select('untappd_url').eq('untappd_url', update['url']).execute()
            if not check.data:
                 print(f"  Creating placeholder in untappd_data for {update['url']}")
                 supabase.table('untappd_data').insert({'untappd_url': update['url'], 'fetched_at': 'now()'}).execute()

    print("Manual linking complete.")

if __name__ == "__main__":
    manual_link()

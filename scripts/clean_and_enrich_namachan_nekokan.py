
import asyncio
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from scripts.enrich_gemini import enrich_gemini

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

async def clean_and_enrich():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    keyword = "なまの猫缶"
    print(f"Searching for items matching: {keyword}")
    
    # 1. Identify valid scraped items matching the name
    res = supabase.table('scraped_beers').select('url, name').ilike('name', f"%{keyword}%").execute()
    
    if not res.data:
        print("❌ No items found matching the keyword.")
        return

    print(f"Found {len(res.data)} items:")
    for item in res.data:
        print(f" - {item['name']} ({item['url']})")
        
        # 2. Clear existing Gemini/Untappd data for these URLs to force fresh processing
        print("   🧹 Clearing gemini_data to force re-enrichment...")
        supabase.table('gemini_data').delete().eq('url', item['url']).execute()
        
        # Also clear untappd_url in scraped_beers
        supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', item['url']).execute()
        
    print("\n🚀 Starting targeted enrichment...")
    # Run enrich_gemini with the keyword filter
    await enrich_gemini(limit=10, keyword_filter=keyword)
    
    print("\n✅ Targeted enrichment completed.")

if __name__ == "__main__":
    asyncio.run(clean_and_enrich())

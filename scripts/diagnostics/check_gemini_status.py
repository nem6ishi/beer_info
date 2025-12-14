import os
import asyncio
from supabase import create_client
from dotenv import load_dotenv

# Load env
load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Env vars missing")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_status():
    print("Checking Gemini enrichment status...")
    
    # 1. Total Missing
    response = supabase.table('beer_info_view') \
        .select('*', count='exact', head=True) \
        .is_('brewery_name_en', 'null') \
        .execute()
    
    total_missing = response.count
    print(f"Total missing Gemini data: {total_missing}")
    
    # 2. Breakdown by Shop (approximate via fetch if not too large, or just separate count queries)
    # Since we can't easily do GROUP BY in supabase-py without RPC, we'll do separate counts for known shops.
    shops = ["一期一会～る", "BEER VOLTA"]
    
    for shop in shops:
        res = supabase.table('beer_info_view') \
            .select('*', count='exact', head=True) \
            .is_('brewery_name_en', 'null') \
            .eq('shop', shop) \
            .execute()
        print(f"  - {shop}: {res.count}")

if __name__ == "__main__":
    check_status()

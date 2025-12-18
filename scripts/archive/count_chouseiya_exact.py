
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def count_exact():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Count strict
    # Shop = 'ちょうせいや'
    # Name contains '【' AND '】'
    
    # We can't do complex ORs (is null or like search) easily in a HEAD request with simple filters depending on lib version.
    # But we can get total brackets count first.
    
    res_total = supabase.table('beer_info_view') \
        .select('*', count='exact', head=True) \
        .eq('shop', 'ちょうせいや') \
        .ilike('name', '%【%】%') \
        .execute()
        
    print(f"Total Chouseiya items with '【...】': {res_total.count}")
    
    # Since we can't easily do the complex filter in HEAD count without writing a function or raw SQL (which we can't do easily with python client without rpc), 
    # let's trust the previous ratio or try to fetch all IDs (lighter payload) to count in python if < 10000.
    
    # Fetch IDs and URLs only, limit 5000
    res_all = supabase.table('beer_info_view') \
        .select('untappd_url') \
        .eq('shop', 'ちょうせいや') \
        .ilike('name', '%【%】%') \
        .limit(5000) \
        .execute()
        
    items = res_all.data
    missing_count = 0
    for item in items:
        u_url = item.get('untappd_url')
        if not u_url or '/search?' in u_url:
            missing_count += 1
            
    print(f"Analyzed {len(items)} items.")
    print(f"Missing Untappd Links: {missing_count}")

if __name__ == "__main__":
    count_exact()

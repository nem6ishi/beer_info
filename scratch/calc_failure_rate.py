import asyncio
from backend.src.core.db import get_supabase_client

def calculate_failure_rate():
    supabase = get_supabase_client()
    
    # 1. Get total unresolved failures
    failures_res = supabase.table('untappd_search_failures').select('id', count='exact').eq('resolved', False).execute()
    total_failures = failures_res.count
    
    # 2. Get total beers
    beers_res = supabase.table('beer_info_view').select('url', count='exact').eq('product_type', 'beer').execute()
    total_beers = beers_res.count
    
    if total_beers == 0:
        print("Total beers is 0.")
        return
        
    percentage = (total_failures / total_beers) * 100
    
    print(f"Total Beers: {total_beers}")
    print(f"Total Untappd Failures: {total_failures}")
    print(f"Failure Rate: {percentage:.2f}%")

if __name__ == "__main__":
    calculate_failure_rate()

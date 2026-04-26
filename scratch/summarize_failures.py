import asyncio
from backend.src.core.db import get_supabase_client
from collections import Counter

def summarize():
    supabase = get_supabase_client()
    
    # Get all failures
    res = supabase.table('untappd_search_failures').select('failure_reason, last_error_message, brewery_name, beer_name, product_url, search_attempts').eq('resolved', False).execute()
    failures = res.data
    
    print(f"Total unresolved failures: {len(failures)}")
    
    reasons = Counter([f['failure_reason'] for f in failures])
    print("\nFailure Reasons:")
    for reason, count in reasons.most_common():
        print(f"  {reason}: {count}")
        
    print("\nSample failures for 'no_results':")
    no_results = [f for f in failures if f['failure_reason'] == 'no_results']
    for f in no_results[:10]:
        print(f"  - Brewery: {f['brewery_name']}, Beer: {f['beer_name']} (URL: {f['product_url']})")

    print("\nSample failures for 'gemini_error':")
    gemini_errors = [f for f in failures if f['failure_reason'] == 'gemini_error']
    for f in gemini_errors[:5]:
        print(f"  - Brewery: {f['brewery_name']}, Beer: {f['beer_name']} (Error: {f['last_error_message']})")

if __name__ == "__main__":
    summarize()

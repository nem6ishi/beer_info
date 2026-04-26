import asyncio
from backend.src.core.db import get_supabase_client

def analyze_recent_failures():
    supabase = get_supabase_client()
    
    # Get failures that were attempted in the recent run but still failed
    res = supabase.table('untappd_search_failures').select('product_url, search_attempts, brewery_name, beer_name, last_error_message').eq('resolved', False).gt('search_attempts', 0).execute()
    failures = res.data
    
    if not failures:
        print("No recent failures found.")
        return
        
    print(f"Found {len(failures)} recent failures:")
    
    # Get gemini data for these
    urls = [f['product_url'] for f in failures[:10]]
    gemini_res = supabase.table('gemini_data').select('*').in_('url', urls).execute()
    gemini_map = {g['url']: g for g in gemini_res.data}
    
    for f in failures[:10]:
        url = f['product_url']
        gemini = gemini_map.get(url, {})
        print(f"\n---")
        print(f"Product: {f['brewery_name']} - {f['beer_name']}")
        print(f"Gemini Brewery: {gemini.get('brewery_name_en')} (JP: {gemini.get('brewery_name_jp')})")
        print(f"Gemini Beer: {gemini.get('beer_name_en')} (JP: {gemini.get('beer_name_jp')})")
        print(f"Error: {f.get('last_error_message')}")
        print(f"URL: {url}")

if __name__ == "__main__":
    analyze_recent_failures()

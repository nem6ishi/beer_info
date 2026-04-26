import asyncio
import logging
from backend.src.core.db import get_supabase_client
from backend.src.services.untappd.searcher import get_untappd_url

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger('backend.src.services.untappd.searcher')
logger.setLevel(logging.DEBUG)

def analyze():
    supabase = get_supabase_client()
    
    # Get 50 unresolved failures
    failures_res = supabase.table('untappd_search_failures').select('product_url, failure_reason, brewery_name, beer_name').eq('resolved', False).limit(50).execute()
    failures = failures_res.data
    
    if not failures:
        print("No failures found.")
        return
        
    urls = [f['product_url'] for f in failures]
    
    beers_res = supabase.table('beer_info_view').select('url, name, beer_name_en, beer_name_jp, brewery_name_en, brewery_name_jp').in_('url', urls).execute()
    beers = {b['url']: b for b in beers_res.data}
    
    print(f"Found {len(failures)} failures to analyze.")
    for i, f in enumerate(failures[:10]): # Analyze 10 first to avoid too long output
        url = f['product_url']
        beer = beers.get(url)
        if not beer:
            continue
            
        brewery = f['brewery_name'] or beer.get('brewery_name_en') or beer.get('brewery_name_jp')
        beer_name = f['beer_name'] or beer.get('beer_name_en') or beer.get('beer_name_jp')
        beer_name_jp = beer.get('beer_name_jp')
        
        print(f"\n[{i+1}] Analzying URL: {url}")
        print(f"  Name: {beer.get('name')}")
        print(f"  Extracted Brewery: {brewery}")
        print(f"  Extracted Beer Name: {beer_name}")
        
        try:
            res = get_untappd_url(
                brewery_name=brewery,
                beer_name=beer_name,
                beer_name_jp=beer_name_jp
            )
            print(f"  Result: {res}")
        except Exception as e:
            print(f"  Exception: {e}")

if __name__ == "__main__":
    analyze()

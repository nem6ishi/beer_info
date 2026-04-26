import asyncio
from backend.src.core.db import get_supabase_client
from collections import Counter

def summarize_by_shop():
    supabase = get_supabase_client()
    
    # Get failures
    res = supabase.table('untappd_search_failures').select('product_url, failure_reason, brewery_name, beer_name').eq('resolved', False).execute()
    failures = res.data
    
    urls = [f['product_url'] for f in failures]
    if not urls:
        print("No failures.")
        return
        
    shop_counts = Counter()
    url_to_shop = {}
    for i in range(0, len(urls), 50):
        chunk = urls[i:i+50]
        beers_res = supabase.table('beer_info_view').select('url, shop').in_('url', chunk).execute()
        for b in beers_res.data:
            url_to_shop[b['url']] = b['shop']
    for f in failures:
        shop = url_to_shop.get(f['product_url'], 'Unknown')
        shop_counts[shop] += 1
        
    shop_examples = {shop: [] for shop in shop_counts.keys()}
    for f in failures:
        shop = url_to_shop.get(f['product_url'], 'Unknown')
        if len(shop_examples[shop]) < 3:
            shop_examples[shop].append(f)
            
    print("\nExamples by shop:")
    for shop, count in shop_counts.most_common():
        print(f"\n[{shop}] ({count} failures)")
        for ex in shop_examples[shop]:
            print(f"  - Brewery: {ex['brewery_name']}, Beer: {ex['beer_name']}")

if __name__ == "__main__":
    summarize_by_shop()

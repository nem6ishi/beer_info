import asyncio
import re
from backend.src.core.db import get_supabase_client
from backend.scripts.audit_precise_store_parsing import parse_shop_english, clean_token

supabase = get_supabase_client()

async def main():
    untappd_dict = {}
    offset = 0
    limit = 1000
    while True:
        res = supabase.table('untappd_data').select('untappd_url, beer_name, brewery_name').range(offset, offset + limit - 1).execute()
        for r in res.data:
            untappd_dict[r['untappd_url']] = r
        if len(res.data) < limit:
            break
        offset += limit

    all_beers = []
    offset = 0
    while True:
        res = supabase.table('scraped_beers').select('url, name, shop, untappd_url, stock_status').not_.is_('untappd_url', 'null').range(offset, offset + limit - 1).execute()
        all_beers.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit

    brewery_mismatches = []
    for b in all_beers:
        shop = b.get('shop')
        name = b.get('name')
        stock = b.get('stock_status')
        u_url = b.get('untappd_url')
        u_data = untappd_dict.get(u_url)
        if not u_data:
            continue
            
        u_brew = (u_data.get('brewery_name') or '').lower()
        s_brew, s_beer = parse_shop_english(shop, name)
        
        if s_brew:
            s_brew_tokens = clean_token(s_brew)
            u_brew_tokens = clean_token(u_brew)
            
            # Common brewery aliases
            if 'westcoast' in s_brew.lower() and 'west coast' in u_brew:
                continue
            if 'うちゅう' in s_brew and 'uchu' in u_brew:
                continue
            if 'vertere' in s_brew.lower() and 'vertere' in u_brew:
                continue
            if 'tamamura' in u_brew and ('志賀高原' in s_brew or 'shiga' in s_brew.lower()):
                continue
            if 'ise' in u_brew and 'ise' in s_brew.lower():
                continue
                
            overlap = s_brew_tokens.intersection(u_brew_tokens)
            if len(s_brew_tokens) >= 1 and len(overlap) == 0:
                brewery_mismatches.append({
                    'url': b['url'],
                    'name': name,
                    'shop': shop,
                    'stock': stock,
                    'store_brew': s_brew,
                    'untappd_brew': u_data.get('brewery_name'),
                    'untappd_beer': u_data.get('beer_name'),
                    'untappd_url': u_url
                })

    print(f"Total Cross-Brewery Mismatches across entire DB: {len(brewery_mismatches)}")
    in_stock = [m for m in brewery_mismatches if m['stock'] == 'In Stock']
    print(f"In Stock: {len(in_stock)}")
    for m in in_stock:
        print(f"  [In Stock] [{m['shop']}] {m['name']} -> Untappd: {m['untappd_brew']} - {m['untappd_beer']}")
        
    print("\nSample Sold Out Cross-Brewery Mismatches (First 20):")
    for m in brewery_mismatches[:20]:
        if m['stock'] != 'In Stock':
            print(f"  [{m['stock']}] [{m['shop']}] {m['name']}")
            print(f"    Store: '{m['store_brew']}' vs Untappd: '{m['untappd_brew']}'")
            print(f"    Current Untappd Beer: {m['untappd_beer']}")
            print(f"    Untappd URL: {m['untappd_url']}")
            print("-" * 50)

if __name__ == '__main__':
    asyncio.run(main())

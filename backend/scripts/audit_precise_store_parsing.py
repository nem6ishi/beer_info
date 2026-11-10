import asyncio
import re
from backend.src.core.db import get_supabase_client
from difflib import SequenceMatcher

supabase = get_supabase_client()

def parse_shop_english(shop: str, name: str):
    """
    Extract the brewery and beer name explicitly provided by each store.
    """
    store_brew = None
    store_beer = None
    
    if shop == "アローム":
        # Format: ... [Brewery / Beer Name]
        m = re.search(r'\[([^/\]]+)\s*/\s*([^\]]+)\]\s*$', name)
        if m:
            store_brew = m.group(1).strip()
            store_beer = m.group(2).strip()
    elif shop == "BEER VOLTA":
        # Format: 日本語 | Brewery: Beer Name
        m = re.search(r'\|\s*([^:]+)\s*:\s*(.+)$', name)
        if m:
            store_brew = m.group(1).strip()
            store_beer = m.group(2).strip()
    elif shop == "WITCH CRAFT MARKET":
        # Format: [Brewery] Beer Name / カタカナ
        m = re.search(r'^\[([^\]]+)\]\s*([^\/]+)(?:\/.*)?$', name)
        if m:
            store_brew = m.group(1).strip()
            store_beer = m.group(2).strip()
    elif shop == "ちょうせいや":
        # Format: 【Beer Name/Brewery】
        # Note: sometimes has %OFF prefix or (賞味期限/...)
        m = re.search(r'【([^/】]+)\s*/\s*([^】]+)】', name)
        if m:
            store_beer = m.group(1).strip()
            store_brew = m.group(2).strip()
            # clean off (賞味期限...)
            store_brew = re.sub(r'[\(（]賞味期限.*', '', store_brew).strip()
    elif shop == "一期一会～る":
        # Format: ...（Brewery Beer Name）
        m = re.search(r'[（\(]([a-zA-Z0-9\s\.\:\,\'\-\&／]+)[）\)]\s*$', name)
        if m:
            full_en = m.group(1).strip()
            # sometimes brewery is the first 1-2 words
            store_beer = full_en
    elif shop == "マルホ酒店":
        # Format: Beer Name (collab w/...) 350ml/Brewery
        m = re.search(r'^(.*?)(?:\s*\d+ml|\s*\(.*?\))*\s*/\s*([^/]+)$', name)
        if m:
            store_beer = m.group(1).strip()
            store_brew = m.group(2).strip()
            
    return store_brew, store_beer

def clean_token(s: str) -> set:
    if not s:
        return set()
    s = s.lower()
    # remove common noise
    s = re.sub(r'[^a-z0-9]', ' ', s)
    tokens = set(s.split())
    tokens -= {
        'the', 'a', 'an', 'and', 'co', 'brewing', 'brewery', 'company',
        'beer', 'beers', 'craft', 'ale', 'ipa', 'dipa', 'tipa', 'hazy',
        'stout', 'sour', 'lager', 'pilsner', 'pils', 'can', 'bottle',
        'ltd', 'inc', 'w', 'collab', 'collaboration', 'edition', 'series'
    }
    return tokens

async def main():
    print("Loading untappd_data...")
    untappd_dict = {}
    offset = 0
    limit = 1000
    while True:
        res = supabase.table('untappd_data').select('untappd_url, beer_name, brewery_name, rating_num').range(offset, offset + limit - 1).execute()
        for r in res.data:
            untappd_dict[r['untappd_url']] = r
        if len(res.data) < limit:
            break
        offset += limit

    print("Loading all scraped_beers...")
    all_beers = []
    offset = 0
    while True:
        res = supabase.table('scraped_beers').select('url, name, shop, untappd_url, stock_status').not_.is_('untappd_url', 'null').range(offset, offset + limit - 1).execute()
        all_beers.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit

    print(f"Auditing {len(all_beers)} beers across all stores...")
    
    confirmed_mismatches = []
    
    for b in all_beers:
        shop = b.get('shop')
        name = b.get('name')
        stock = b.get('stock_status')
        u_url = b.get('untappd_url')
        u_data = untappd_dict.get(u_url)
        if not u_data:
            continue
            
        u_beer = u_data.get('beer_name') or ''
        u_brew = u_data.get('brewery_name') or ''
        
        s_brew, s_beer = parse_shop_english(shop, name)
        
        if not s_beer:
            continue
            
        s_beer_tokens = clean_token(s_beer)
        u_beer_tokens = clean_token(u_beer)
        
        # If store specifies brewery, remove brewery words from beer tokens
        if s_brew:
            s_brew_tokens = clean_token(s_brew)
            s_beer_tokens -= s_brew_tokens
            
        # check overlap
        overlap = s_beer_tokens.intersection(u_beer_tokens)
        
        # Condition for high confidence mismatch:
        # Store beer has at least 2 significant distinct keywords, but ZERO overlap with Untappd beer
        if len(s_beer_tokens) >= 2 and len(overlap) == 0:
            # check string similarity as well
            ratio = SequenceMatcher(None, ' '.join(sorted(s_beer_tokens)), ' '.join(sorted(u_beer_tokens))).ratio()
            if ratio < 0.35:
                confirmed_mismatches.append({
                    'shop': shop,
                    'stock': stock,
                    'raw_name': name,
                    'extracted_brew': s_brew,
                    'extracted_beer': s_beer,
                    'untappd_brew': u_brew,
                    'untappd_beer': u_beer,
                    'untappd_url': u_url,
                    'ratio': ratio,
                    'tokens_store': s_beer_tokens,
                    'tokens_untappd': u_beer_tokens
                })

    print(f"\n==================================================")
    print(f"Total High-Confidence Mismatches Found: {len(confirmed_mismatches)}")
    in_stock = [m for m in confirmed_mismatches if m['stock'] == 'In Stock']
    sold_out = [m for m in confirmed_mismatches if m['stock'] != 'In Stock']
    print(f"  -> In Stock: {len(in_stock)}")
    print(f"  -> Sold Out: {len(sold_out)}")
    print(f"==================================================\n")

    if in_stock:
        print("🚨 IN STOCK MISMATCHES:")
        for i, m in enumerate(in_stock, 1):
            print(f"{i}. [{m['shop']}] {m['raw_name']}")
            print(f"   Extracted Store Beer: {m['extracted_beer']}")
            print(f"   Current Untappd: {m['untappd_brew']} - {m['untappd_beer']}")
            print(f"   URL: {m['untappd_url']}")
            print("-" * 50)

    print("\n🔍 SAMPLE SOLD OUT MISMATCHES (First 30):")
    for i, m in enumerate(sold_out[:30], 1):
        print(f"{i}. [{m['stock']}] [{m['shop']}] {m['raw_name']}")
        print(f"   Extracted Store Beer: {m['extracted_beer']}")
        print(f"   Current Untappd: {m['untappd_brew']} - {m['untappd_beer']}")
        print(f"   URL: {m['untappd_url']}")
        print("-" * 50)

if __name__ == '__main__':
    asyncio.run(main())

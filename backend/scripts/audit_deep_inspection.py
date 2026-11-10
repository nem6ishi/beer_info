import asyncio
import re
from collections import defaultdict
from difflib import SequenceMatcher
from backend.src.core.db import get_supabase_client

supabase = get_supabase_client()

def clean_beer_title(name: str) -> str:
    if not name:
        return ""
    # Remove store prefixes / notes
    s = re.sub(r'【.*?】|\[.*?\]|（.*?）|\(.*?\)', ' ', name)
    s = re.sub(r'\d+ml|\d+缶|\d+瓶|パイント|缶|瓶', ' ', s, flags=re.I)
    s = re.sub(r'\d{4}\.\d{2}(\.\d{2})?|\d{4}年\d+月(入荷)?', ' ', s)
    s = re.sub(r'ipa|dipa|tipa|stout|sour|hazy|ale|lager|pilsner', ' ', s, flags=re.I)
    s = re.sub(r'collab\s+w/.*', ' ', s, flags=re.I)
    s = re.sub(r'[^a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', ' ', s)
    return " ".join(s.lower().split())

async def run_audit():
    print("Fetching all scraped_beers and untappd_data...")
    
    # 1. Fetch all untappd_data
    untappd_dict = {}
    offset = 0
    limit = 1000
    while True:
        res = supabase.table('untappd_data').select('untappd_url, beer_name, brewery_name, abv_num, rating_num').range(offset, offset + limit - 1).execute()
        for r in res.data:
            untappd_dict[r['untappd_url']] = r
        if len(res.data) < limit:
            break
        offset += limit
    print(f"Loaded {len(untappd_dict)} untappd_data records.")

    # 2. Fetch all scraped_beers
    all_beers = []
    offset = 0
    while True:
        res = supabase.table('scraped_beers').select('url, name, shop, untappd_url, stock_status').not_.is_('untappd_url', 'null').range(offset, offset + limit - 1).execute()
        all_beers.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit
    print(f"Loaded {len(all_beers)} scraped_beers with untappd_url.")

    mismatches = []
    
    # Check 1: Extract ABV from name if available and compare
    abv_pattern = re.compile(r'(\d{1,2}(?:\.\d{1,2})?)\s*%\s*(?:abv)?', re.I)
    
    for b in all_beers:
        u_url = b.get('untappd_url')
        u_data = untappd_dict.get(u_url)
        if not u_data:
            continue
        
        name = b.get('name') or ''
        stock = b.get('stock_status')
        shop = b.get('shop')
        
        u_beer = u_data.get('beer_name') or ''
        u_brew = u_data.get('brewery_name') or ''
        u_abv = u_data.get('abv_num')
        
        # Check ABV mismatch (> 1.8% difference)
        abv_matches = abv_pattern.findall(name)
        if abv_matches and u_abv is not None:
            # find first reasonable beer ABV (usually between 3.0 and 20.0)
            for m_str in abv_matches:
                try:
                    val = float(m_str)
                    if 3.0 <= val <= 20.0:
                        diff = abs(val - u_abv)
                        if diff >= 2.0:
                            mismatches.append({
                                'category': 'ABV Mismatch',
                                'shop': shop,
                                'stock': stock,
                                'name': name,
                                'u_brew': u_brew,
                                'u_beer': u_beer,
                                'u_url': u_url,
                                'detail': f"Raw name mentions {val}% ABV but Untappd is {u_abv}% ABV (diff: {diff:.1f}%)"
                            })
                            break
                except ValueError:
                    pass

        # Check Name Discrepancy
        # English distinct tokens in name
        c_name = name.lower()
        # Find explicit English title if present in parentheses e.g. （Modern Times Pause for Effect）
        en_paren = re.search(r'[（\(]([a-zA-Z0-9\s\.\:\,\'\-\&]+)[）\)]', name)
        raw_en = en_paren.group(1).lower() if en_paren else ""
        
        if raw_en and len(raw_en.strip()) > 3:
            # exclude brewery name if present
            # check token overlap with u_beer
            u_beer_lower = u_beer.lower()
            u_brew_lower = u_brew.lower()
            
            raw_en_tokens = set(re.findall(r'[a-z0-9]+', raw_en))
            raw_en_tokens -= {'the', 'a', 'an', 'and', 'co', 'brewing', 'brewery', 'company', 'can', 'pint', 'uk', 'vol', 'w'}
            raw_en_tokens -= set(re.findall(r'[a-z0-9]+', u_brew_lower))
            
            u_beer_tokens = set(re.findall(r'[a-z0-9]+', u_beer_lower))
            u_beer_tokens -= {'the', 'a', 'an', 'and', 'ipa', 'dipa', 'ale'}
            
            overlap = raw_en_tokens.intersection(u_beer_tokens)
            # If raw English name has 2+ solid words and ZERO overlap with untappd beer name
            if len(raw_en_tokens) >= 2 and len(overlap) == 0:
                mismatches.append({
                    'category': 'Beer Name In English Parentheses Mismatch',
                    'shop': shop,
                    'stock': stock,
                    'name': name,
                    'u_brew': u_brew,
                    'u_beer': u_beer,
                    'u_url': u_url,
                    'detail': f"English in parentheses '{raw_en.strip()}' has no common words with Untappd beer '{u_beer}'"
                })

    print(f"\nTotal potential mismatches detected: {len(mismatches)}")
    
    in_stock_mismatches = [m for m in mismatches if m['stock'] == 'In Stock']
    print(f"  -> In Stock mismatches: {len(in_stock_mismatches)}")
    print(f"  -> Out of Stock mismatches: {len(mismatches) - len(in_stock_mismatches)}")

    # Group by category and print
    by_cat = defaultdict(list)
    for m in mismatches:
        by_cat[m['category']].append(m)

    for cat, items in by_cat.items():
        print(f"\n==================== {cat} ({len(items)} items) ====================")
        # Show in-stock items first!
        sorted_items = sorted(items, key=lambda x: (x['stock'] != 'In Stock', x['shop']))
        for i, item in enumerate(sorted_items[:30], 1):
            print(f"{i}. [{item['stock']}] [{item['shop']}] {item['name']}")
            print(f"   -> Untappd: {item['u_brew']} - {item['u_beer']}")
            print(f"   -> Detail: {item['detail']}")
            print(f"   -> URL: {item['u_url']}")
            print("-" * 50)
        if len(sorted_items) > 30:
            print(f"... and {len(sorted_items) - 30} more items in this category.")

if __name__ == '__main__':
    asyncio.run(run_audit())

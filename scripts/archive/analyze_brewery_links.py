import os
import sys
from dotenv import load_dotenv
from supabase import create_client
from collections import defaultdict

# Load env robustness
# Try current dir first, then parent
if os.path.exists('.env'):
    load_dotenv('.env')
elif os.path.exists('../.env'):
    load_dotenv('../.env')
else:
    # Hard fallback to expected path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    env_path = os.path.join(parent_dir, '.env')
    load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL:
    print("Error: SUPABASE_URL not found in env.")
    sys.exit(1)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def analyze_links():
    print("Fetching untappd_data...")
    # Fetch all for analysis (might be large, but acceptable for this scale)
    res = supabase.table('untappd_data').select('beer_name, brewery_name, untappd_brewery_url').execute()
    data = res.data
    
    brewery_map = defaultdict(lambda: {'has_url': 0, 'missing_url': 0, 'url': None})
    
    for item in data:
        b_name = item.get('brewery_name')
        b_url = item.get('untappd_brewery_url')
        
        if not b_name: continue
        
        if b_url:
            brewery_map[b_name]['has_url'] += 1
            if not brewery_map[b_name]['url']:
                 brewery_map[b_name]['url'] = b_url
            elif brewery_map[b_name]['url'] != b_url:
                 print(f"WARNING: Multiple URLs for {b_name}: {brewery_map[b_name]['url']} vs {b_url}")
        else:
            brewery_map[b_name]['missing_url'] += 1

    print(f"\nAnalysis Results ({len(brewery_map)} unique brewery names):")
    print(f"{'Brewery Name':<40} | {'Has URL':<8} | {'Missing':<8} | {'Suggested URL'}")
    print("-" * 100)
    
    potential_fixes = 0
    for name, stats in brewery_map.items():
        if stats['missing_url'] > 0 and stats['has_url'] > 0:
            print(f"{name[:40]:<40} | {stats['has_url']:<8} | {stats['missing_url']:<8} | {stats['url']}")
            potential_fixes += stats['missing_url']
            
    print("-" * 100)
    print(f"Total potential backfills: {potential_fixes}")

if __name__ == "__main__":
    analyze_links()

import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.utils.script_utils import setup_script

def check_red_ipa():
    supabase, logger = setup_script("find_red_ipa")
    search_term = "Red IPA"
    res = supabase.table('scraped_beers').select('*').ilike('name', f'%{search_term}%').execute()
    print(f"Found {len(res.data)} items matching '{search_term}':")
    for item in res.data:
        print(f"- ID: {item.get('id')} / Name: {item.get('name')} / Shop: {item.get('shop')} / URL: {item.get('url')}")
        print(f"  Untappd URL: {item.get('untappd_url')}")

if __name__ == '__main__':
    check_red_ipa()

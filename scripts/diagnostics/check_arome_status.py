import sys
import os

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from lib.supabase import supabase

def check_arome():
    res = supabase.table('beer_info_view').select('url', count='exact').eq('shop', 'Arôme').not_.is_('untappd_url', 'null').execute()
    print(f"Total Arôme beers with Untappd URL: {res.count}")
    
    res_all = supabase.table('scraped_beers').select('url', count='exact').eq('shop', 'Arôme').execute()
    print(f"Total Arôme beers in DB: {res_all.count}")

if __name__ == '__main__':
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.append(project_root)
    
    check_arome()

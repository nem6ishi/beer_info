import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from scripts.utils.script_utils import setup_script

def count_missing():
    supabase, logger = setup_script("CountMissing")
    
    res = supabase.table('untappd_data').select('untappd_url', count='exact').is_('untappd_brewery_url', 'null').execute()
    print(f"Beers with Missing Brewery Links: {res.count}")

if __name__ == "__main__":
    count_missing()

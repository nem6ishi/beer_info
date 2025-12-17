import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from scripts.utils.script_utils import setup_script

def check_untappd_data():
    supabase, logger = setup_script("CheckUntappd")
    
    untappd_url = "https://untappd.com/b/and-beer-tamiru-tadesse-coffee-ale/6488346"
    
    logger.info(f"Checking untappd_data for {untappd_url}...")
    
    response = supabase.table('untappd_data').select("*").eq('untappd_url', untappd_url).execute()
    
    if response.data:
        data = response.data[0]
        print(f"---")
        print(f"Beer Name: {data.get('beer_name')}")
        print(f"Brewery Name: {data.get('brewery_name')}")
        print(f"Untappd Brewery URL: {data.get('untappd_brewery_url')}")
        
        if data.get('untappd_brewery_url'):
            brewery_url = data.get('untappd_brewery_url')
            print(f"Checking brewery table for {brewery_url}...")
            b_resp = supabase.table('breweries').select("*").eq('untappd_url', brewery_url).execute()
            if b_resp.data:
                print(f"Brewery found in 'breweries' table: {b_resp.data[0].get('name_en')}")
            else:
                print("Brewery NOT found in 'breweries' table.")
    else:
        logger.warning("No entry found in untappd_data!")

if __name__ == "__main__":
    check_untappd_data()

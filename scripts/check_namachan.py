
import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_beer():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    keyword = "なまの猫缶"
    print(f"Searching for '%{keyword}%'...")
    
    response = supabase.table('beer_info_view') \
        .select('*') \
        .ilike('name', f'%{keyword}%') \
        .limit(10) \
        .execute()
        
    items = response.data
    for item in items:
        print("---")
        print(f"Name: {item.get('name')}")
        print(f"Brewery (Gemini EN): {item.get('brewery_name_en')}")
        print(f"Brewery (Gemini JP): {item.get('brewery_name_jp')}")
        print(f"Beer (Gemini EN): {item.get('beer_name_en')}")
        print(f"Beer (Gemini JP): {item.get('beer_name_jp')}")
        print(f"Untappd URL: {item.get('untappd_url')}")
        print("---")

if __name__ == "__main__":
    check_beer()


import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_brewery_db():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("Searching for 'Namachan' or 'NAMACHA' in breweries...")
    
    # Search by name_en or aliases
    # Supabase simple filter doesn't support ILIKE on array column easily for aliases without rpc
    # So we fetch all and search in python or search name_en first
    
    res = supabase.table('breweries').select('*').ilike('name_en', '%Namacha%').execute()
    
    found = False
    for b in res.data:
        found = True
        print(f"Found Brewery: {b['name_en']}")
        print(f"  JP Name: {b['name_jp']}")
        print(f"  Aliases: {b['aliases']}")
        print("-" * 20)
        
    if not found:
        print("No brewery found matching 'Namacha' in name_en.")

if __name__ == "__main__":
    check_brewery_db()

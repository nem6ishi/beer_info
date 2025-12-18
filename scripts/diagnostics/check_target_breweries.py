import os
from supabase import create_client, Client
from dotenv import load_dotenv

def check_breweries():
    # Load environment variables
    env_path = os.path.join(os.getcwd(), '.env')
    load_dotenv(env_path)

    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        return

    supabase: Client = create_client(supabase_url, supabase_key)
    
    target_names = ["Craftrock Brewing", "Yuya Boys"]
    
    for name in target_names:
        print(f"\nChecking brewery: {name}")
        # Search by name_en or name_jp
        response = supabase.table('breweries').select('*').or_(f"name_en.ilike.%{name}%,name_jp.ilike.%{name}%").execute()
        
        if not response.data:
            print(f"  No brewery found matching '{name}'")
            continue
            
        for brewery in response.data:
            print(f"  Found: ID={brewery.get('id')}, EN={brewery.get('name_en')}, JP={brewery.get('name_jp')}")
            print(f"  Logo URL: {brewery.get('logo_url')}")
            print(f"  Untappd URL: {brewery.get('untappd_url')}")
            print(f"  Location: {brewery.get('location')}")

if __name__ == "__main__":
    check_breweries()

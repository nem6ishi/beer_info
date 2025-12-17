
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

def check_aliases():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Fetch all breweries with aliases
    res = supabase.table('breweries').select('name_en, aliases').execute()
    
    problematic = []
    suspicious_aliases = {'Black', 'West', 'East', 'North', 'South', 'The', 'New', 'Old', 'Blue', 'Red', 'Green'}
    
    for b in res.data:
        aliases = b.get('aliases') or []
        name = b.get('name_en')
        
        found = []
        for a in aliases:
            if a in suspicious_aliases or len(a) < 3:
                found.append(a)
        
        if found:
            problematic.append(f"Brewery: {name} | Bad Aliases: {found}")

    print(f"Found {len(problematic)} breweries with suspicious aliases:")
    for p in problematic:
        print(p)

if __name__ == "__main__":
    check_aliases()


import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials not found.")
    sys.exit(1)

def count_missing_untappd():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    print("Querying Chouseiya items with '【' and '】' in name...")
    
    # We want: 
    # Shop = 'ちょうせいや'
    # Name contains '【' AND '】'
    # Untappd URL is NULL OR Untappd URL contains '/search?'
    
    # Supabase-py doesn't support complex nested ORs easily in one go with the JS-like syntax unless we use RPC or raw SQL or careful chaining.
    # However, we can use the .or_() filter on top level columns if needed, or fetch and filter in python if the dataset is small enough (Chouseiya is ~1500 items, small enough).
    # But let's try to filter as much as possible in DB.
    
    # Fetch all Chouseiya items that have the brackets
    response = supabase.table('beer_info_view') \
        .select('name, untappd_url') \
        .eq('shop', 'ちょうせいや') \
        .ilike('name', '%【%】%') \
        .execute()
        
    items = response.data
    total_bracket_items = len(items)
    
    missing_count = 0
    examples = []
    
    print(f"Total items with brackets: {total_bracket_items}")
    
    for item in items:
        u_url = item.get('untappd_url')
        # Check if missing or search link
        if not u_url or '/search?' in u_url:
            missing_count += 1
            if len(examples) < 5:
                examples.append(item)
    
    print(f"Items missing Untappd link (NULL or Search result): {missing_count}")
    print("-" * 30)
    print("Examples:")
    for ex in examples:
        print(f"Name: {ex['name']}")
        print(f"URL: {ex.get('untappd_url')}")
        print("")

if __name__ == "__main__":
    count_missing_untappd()

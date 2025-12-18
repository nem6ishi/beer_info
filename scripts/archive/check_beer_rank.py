
import os
import sys
from supabase import create_client

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

target_name = "【必ず合計「6本」以上になるようご注文下さい】志賀高原ビール×オックスボウ　山伏　OSMK！（SHIGA KOGEN YAMABUSHI OSMK!）"
print(f"Target: {target_name}")

# Fetch all keys to sort locally or use DB rank? 
# Using python for flexibility with exact string match
print("Fetching all beers ordered by first_seen desc...")
# Fetch ID and Name only to be fast
res = supabase.table('scraped_beers').select('name, first_seen').order('first_seen', desc=True).limit(1000).execute()

found_rank = -1
if res.data:
    for i, item in enumerate(res.data, 1):
        if item['name'] == target_name:
            found_rank = i
            break
        # Also try partial match just in case
        if "OSMK" in item['name'] and "志賀高原" in item['name']:
             print(f"Potential match at {i}: {item['name']}")
             if found_rank == -1: found_rank = i # Set if not exact found yet (though exact is preferred)

if found_rank != -1:
    print(f"\nFOUND! Rank: {found_rank}")
else:
    print("\nNOT FOUND in top 1000.")

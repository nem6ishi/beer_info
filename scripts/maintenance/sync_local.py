#!/usr/bin/env python3
"""
Sync Supabase data to local JSON file (data/beers.json)
"""
import os
import sys
import json
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "beers.json")

def sync_from_supabase():
    print("=" * 60)
    print("📥 Syncing from Supabase to local JSON")
    print("=" * 60)
    
    # Get Supabase credentials
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_KEY must be set")
        sys.exit(1)
        
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # Fetch all data (handling pagination if necessary, though Supabase has limits)
    # Default limit is usually 1000, we might need loops if we have more
    print("Fetching data from Supabase...")
    
    all_beers = []
    page = 0
    page_size = 1000
    
    while True:
        start = page * page_size
        end = start + page_size - 1
        
        response = supabase.table('beers').select('*').range(start, end).execute()
        data = response.data
        
        if not data:
            break
            
        all_beers.extend(data)
        print(f"  Fetched {len(data)} rows (Total: {len(all_beers)})")
        
        if len(data) < page_size:
            break
            
        page += 1
    
    print(f"\n✅ Fetched {len(all_beers)} total beers")
    
    # Save to JSON
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_beers, f, indent=4, ensure_ascii=False)
        
    print(f"💾 Saved to {OUTPUT_FILE}")
    print(f"Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

if __name__ == "__main__":
    sync_from_supabase()

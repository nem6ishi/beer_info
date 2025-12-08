#!/usr/bin/env python3
"""
Clear all data from the database.
"""
import os
import sys
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def clear_database():
    print("=" * 60)
    print("🗑️  CLEARING DATABASE")
    print("=" * 60)
    
    # Get Supabase credentials
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) and SUPABASE_SERVICE_KEY must be set")
        sys.exit(1)
        
    supabase: Client = create_client(supabase_url, supabase_key)
    
    print("⚠️  This will delete ALL data from the 'beers' table.")
    confirm = input("Are you sure? (Type 'yes' to confirm): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return

    try:
        # Delete all records where ID is not null (effectively all)
        response = supabase.table('beers').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        # Note: Depending on RLS and table size, this might need multiple batches or a different approach.
        # neq uuid-zero is a common trick if 'id' is required/PK.
        
        count = len(response.data) if response.data else 0
        print(f"✅ Deleted {count} records.")
        print(f"Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
    except Exception as e:
        print(f"Error clearing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    clear_database()

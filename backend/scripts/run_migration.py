#!/usr/bin/env python3
"""
Run a SQL migration file against Supabase.
"""
import sys
from pathlib import Path
from backend.src.core.db import get_supabase_client


def run_migration(sql_file_path: str):
    """Execute a SQL migration file."""
    sql_path = Path(sql_file_path)
    
    if not sql_path.exists():
        print(f"❌ Error: File not found: {sql_file_path}")
        return 1
    
    print(f"📄 Reading migration file: {sql_path.name}")
    sql_content = sql_path.read_text()
    
    print(f"🔄 Executing migration...")
    supabase = get_supabase_client()
    
    try:
        # Supabase Python client doesn't support raw SQL execution directly
        # We need to use rpc() or execute SQL via REST API
        # For now, print instructions for manual execution
        print("\n" + "="*70)
        print("⚠️  Manual Migration Required")
        print("="*70)
        print("\nSupabase Python client doesn't support direct SQL execution.")
        print("Please run this migration manually in one of these ways:\n")
        print("1. Supabase Dashboard:")
        print("   - Navigate to SQL Editor")
        print("   - Copy and paste the content below")
        print("   - Click 'Run'\n")
        print("2. psql command line:")
        print("   - Connect to your Supabase database")
        print(f"   - Run: \\i {sql_path.absolute()}\n")
        print("="*70)
        print("\nSQL Content to execute:\n")
        print(sql_content)
        print("\n" + "="*70)
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <path/to/migration.sql>")
        sys.exit(1)
    
    sys.exit(run_migration(sys.argv[1]))

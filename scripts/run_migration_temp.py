import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def run_sql():
    # Attempt to read the SQL file
    try:
        with open('migrations/create_scraper_metadata.sql', 'r') as f:
            sql = f.read()
    except FileNotFoundError:
        print("SQL file not found.")
        sys.exit(1)

    print("Executing SQL...")
    # Since supabase-py controls data via REST, running raw DDL is tricky.
    # However, supabase-py client *might* not support raw SQL unless via RPC.
    # BUT, the user environment often has 'psycopg2' if it's a python env.
    
    # Try importing psycopg2
    try:
        import psycopg2
        
        # We need the connection string.
        # Check env for SUPABASE_DB_URL or DATABASE_URL
        db_url = os.getenv('SUPABASE_DB_URL') or os.getenv('DATABASE_URL')
        if not db_url:
            # Construct it from project ref if possible? No, need password.
            # Usually DATABASE_URL is provided in .env
            print("DATABASE_URL or SUPABASE_DB_URL not found in .env. Cannot verify connection string.")
            print("Please ensure you have a standard Postgres connection string.")
            # Fallback: Print instruction
            print(f"\nPlease run the following SQL manually in your Supabase SQL Editor:\n\n{sql}")
            return

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ SQL Executed successfully via psycopg2.")
        
    except ImportError:
        print("psycopg2 not installed. Cannot run SQL directly.")
        print(f"\nPlease run the following SQL manually in your Supabase SQL Editor:\n\n{sql}")

if __name__ == "__main__":
    run_sql()

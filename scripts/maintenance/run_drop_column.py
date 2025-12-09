import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

def run_sql():
    try:
        with open('migrations/remove_restocked_at.sql', 'r') as f:
            sql = f.read()
    except FileNotFoundError:
        print("SQL file not found.")
        sys.exit(1)

    print("Executing SQL...")
    try:
        import psycopg2
        db_url = os.getenv('SUPABASE_DB_URL') or os.getenv('DATABASE_URL')
        if not db_url:
            print("DATABASE_URL or SUPABASE_DB_URL not found in .env.")
            print(f"\nPlease run manually:\n\n{sql}")
            return

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ SQL Executed successfully via psycopg2.")
        
    except ImportError:
        print("psycopg2 not installed.")
        print(f"\nPlease run manually:\n\n{sql}")

if __name__ == "__main__":
    run_sql()

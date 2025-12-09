import os
import sys
import psycopg2
from dotenv import load_dotenv

# Load env from root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

def run_migration(sql_file_path):
    if not os.path.exists(sql_file_path):
        print(f"Error: SQL file {sql_file_path} not found.")
        sys.exit(1)

    with open(sql_file_path, 'r') as f:
        sql = f.read()

    db_url = os.getenv('SUPABASE_DB_URL') or os.getenv('DATABASE_URL')
    
    if not db_url:
        print("Error: DATABASE_URL not found in .env")
        print("Please run the following SQL manually:")
        print("-" * 50)
        print(sql)
        print("-" * 50)
        sys.exit(1)

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print(f"Executing {sql_file_path}...")
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ SQL Executed successfully.")
    except Exception as e:
        print(f"Error executing SQL: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 run_db_migration.py <path_to_sql_file>")
        sys.exit(1)
    
    run_migration(sys.argv[1])


import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('.env')

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

if not url or not key:
    print("Error: Missing Supabase credentials in .env.local")
    exit(1)

supabase = create_client(url, key)

def check_abv_format():
    print("Checking ABV format in untappd_data...")
    try:
        # Fetch up to 1000 rows to be sure
        response = supabase.table('untappd_data').select('abv').limit(1000).execute()
        data = response.data
        
        non_numeric = []
        numeric_count = 0
        
        for row in data:
            abv = row.get('abv')
            if abv:
                # Remove potential '%' sign
                clean_abv = abv.replace('%', '').strip()
                try:
                    float(clean_abv)
                    numeric_count += 1
                except ValueError:
                    non_numeric.append(abv)
        
        print(f"Checked {len(data)} rows.")
        print(f"Numeric values: {numeric_count}")
        
        if non_numeric:
            print(f"FOUND {len(non_numeric)} non-numeric ABV values. Examples:")
            for val in non_numeric[:10]:
                print(f" - '{val}'")
        else:
            print("All checked ABV values are valid numbers (potentially with %).")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_abv_format()

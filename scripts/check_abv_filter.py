
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv('.env')

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
supabase = create_client(url, key)

def check_abv_filter():
    print("Checking ABV filter (min_abv=10)...")
    try:
        response = supabase.table('beer_info_view') \
            .select('*') \
            .gte('untappd_abv', 10) \
            .limit(20) \
            .execute()
        
        data = response.data
        print(f"Returned {len(data)} beers.")
        
        failed = []
        for beer in data:
            abv = beer.get('untappd_abv')
            try:
                # Handle % and N/A
                val = float(abv.replace('%', '').strip())
                if val < 10:
                    failed.append(f"{beer.get('name')} (ABV: {abv})")
            except:
                pass # N/A etc.
        
        if failed:
            print(f"FAILED: Found {len(failed)} beers with ABV < 10 despite filter:")
            for f in failed[:5]:
                print(f" - {f}")
        else:
            print("SUCCESS: All returned beers have ABV >= 10.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_abv_filter()

# scratch/check_breweries_db.py
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.core.db import get_supabase_client

def main():
    supabase = get_supabase_client()
    print("Searching breweries table...")
    
    # 検索キーワード
    keywords = ["falo", "vertere", "8bit", "8 bit", "oriental", "tono", "hiruzen", "two rabbits"]
    
    try:
        response = supabase.table("breweries").select("*").limit(1000).execute()
        breweries = response.data
        print(f"Loaded {len(breweries)} breweries from DB.")
        
        for kw in keywords:
            print(f"\nMatches for keyword: '{kw}'")
            print("-" * 50)
            found = False
            for b in breweries:
                name_en = (b.get("name_en") or "").lower()
                name_jp = (b.get("name_jp") or "").lower()
                aliases = [a.lower() for a in (b.get("aliases") or [])]
                
                if kw in name_en or kw in name_jp or any(kw in a for a in aliases):
                    print(f"ID: {b.get('id')}")
                    print(f"  Name (EN): {b.get('name_en')}")
                    print(f"  Name (JP): {b.get('name_jp')}")
                    print(f"  Aliases  : {b.get('aliases')}")
                    print(f"  Untappd  : {b.get('untappd_url')}")
                    found = True
            if not found:
                print("No matches.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

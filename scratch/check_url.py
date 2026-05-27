# scratch/check_url.py
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.core.db import get_supabase_client

def check(url):
    supabase = get_supabase_client()
    print(f"Checking URL in database: {url}")
    
    try:
        # scraped_beers
        res1 = supabase.table("scraped_beers").select("*").eq("url", url).maybe_single().execute()
        if res1.data:
            print("--- scraped_beers ---")
            for k, v in res1.data.items():
                print(f"  {k}: {v}")

        # gemini_data
        res3 = supabase.table("gemini_data").select("*").eq("url", url).maybe_single().execute()
        if res3.data:
            print("\n--- gemini_data ---")
            for k, v in res3.data.items():
                print(f"  {k}: {v}")
        else:
            print("\nNot found in gemini_data")

        # untappd_search_failures
        res2 = supabase.table("untappd_search_failures").select("*").eq("product_url", url).maybe_single().execute()
        if res2.data:
            print("\n--- untappd_search_failures ---")
            for k, v in res2.data.items():
                print(f"  {k}: {v}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check("https://151l.shop/?pid=191879914")

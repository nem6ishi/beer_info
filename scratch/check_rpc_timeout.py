import os
import time
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def check_queries():
    print("Testing API queries directly using Supabase Python Client...")
    
    # パラメータ設定
    # shop='アローム', min_abv=4.5, max_abv=8.5, stock_filter='in_stock'
    shop = "アローム"
    min_abv = 4.5
    max_abv = 8.5
    stock_filter = "in_stock"
    
    # 1. メインクエリのテスト
    print("\n--- 1. Testing Main Query (beer_info_view) ---")
    start = time.time()
    try:
        q = supabase.table("beer_info_view").select("*", count="exact")
        q = q.gte("untappd_abv", min_abv)
        q = q.lte("untappd_abv", max_abv)
        q = q.in_("shop", [shop])
        q = q.eq("stock_status", "In Stock")
        res = q.range(0, 49).execute()
        duration = time.time() - start
        print(f"Main Query Success! Count: {res.count}, Items: {len(res.data)}, Time: {duration:.3f}s")
    except Exception as e:
        print(f"Main Query Failed: {e}")

    # 2. RPC (get_filtered_shop_counts) のテスト
    print("\n--- 2. Testing RPC (get_filtered_shop_counts) ---")
    start = time.time()
    try:
        res = supabase.rpc("get_filtered_shop_counts", {
            "search_query": None,
            "p_min_abv": min_abv,
            "p_max_abv": max_abv,
            "p_min_ibu": None,
            "p_max_ibu": None,
            "p_min_rating": None,
            "p_stock_filter": stock_filter,
            "p_style_filter": None,
            "p_brewery_filter": None,
            "p_product_type": None,
            "p_untappd_status": None
        }).execute()
        duration = time.time() - start
        print(f"RPC Success! Results: {len(res.data)}, Time: {duration:.3f}s")
        print("Data:", res.data)
    except Exception as e:
        print(f"RPC Failed: {e}")

if __name__ == "__main__":
    check_queries()

#!/usr/bin/env python3
"""
特定の商品名で検索
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db import get_supabase_client

def search_product(product_name):
    supabase = get_supabase_client()
    
    print(f"🔍 検索中: '{product_name}'")
    print("=" * 80)
    
    # beer_info_view で検索
    print("\n📊 商品情報:")
    res = supabase.from_('beer_info_view') \
        .select('*') \
        .ilike('name', f'%{product_name}%') \
        .limit(5) \
        .execute()
    
    if res.data:
        for item in res.data:
            print(f"\n  商品名: {item.get('name')}")
            print(f"  店舗: {item.get('shop')}")
            print(f"  is_set: {item.get('is_set')}")
            print(f"  brewery_name_en: {item.get('brewery_name_en')}")
            print(f"  brewery_name_jp: {item.get('brewery_name_jp')}")
            print(f"  beer_name_en: {item.get('beer_name_en')}")
            print(f"  beer_name_jp: {item.get('beer_name_jp')}")
            print(f"  untappd_brewery_name: {item.get('untappd_brewery_name')}")
            print(f"  untappd_beer_name: {item.get('untappd_beer_name')}")
            print(f"  untappd_url: {item.get('untappd_url')}")
            print(f"  untappd_rating: {item.get('untappd_rating')}")
    else:
        print(f"  ❌ '{product_name}' は見つかりません")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "カンティヨン"
    search_product(query)

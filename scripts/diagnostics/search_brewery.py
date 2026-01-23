#!/usr/bin/env python3
"""
特定のブルワリーを検索
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db import get_supabase_client

def search_brewery(brewery_name):
    supabase = get_supabase_client()
    
    print(f"🔍 検索中: '{brewery_name}'")
    print("=" * 80)
    
    # 1. breweries テーブルで検索
    print("\n📊 breweries テーブル:")
    breweries_res = supabase.table('breweries') \
        .select('*') \
        .ilike('name_en', f'%{brewery_name}%') \
        .execute()
    
    if breweries_res.data:
        for b in breweries_res.data:
            print(f"  ✅ 登録済み:")
            print(f"     名前: {b.get('name_en')}")
            print(f"     URL: {b.get('untappd_url')}")
            print(f"     ロゴ: {b.get('logo_url')}")
            print(f"     場所: {b.get('location')}")
            print(f"     更新日: {b.get('updated_at')}")
    else:
        print(f"  ❌ breweries テーブルに '{brewery_name}' は見つかりません")
    
    # 2. untappd_data テーブルで検索
    print(f"\n📊 untappd_data テーブル:")
    untappd_res = supabase.table('untappd_data') \
        .select('brewery_name, untappd_brewery_url, beer_name') \
        .ilike('brewery_name', f'%{brewery_name}%') \
        .limit(10) \
        .execute()
    
    if untappd_res.data:
        print(f"  ✅ {len(untappd_res.data)} 件のビールが見つかりました:")
        brewery_urls = set()
        for item in untappd_res.data:
            brewery_urls.add((item.get('brewery_name'), item.get('untappd_brewery_url')))
        
        for brewery_name_found, url in brewery_urls:
            print(f"     ブルワリー名: {brewery_name_found}")
            print(f"     URL: {url}")
            
            # このURLがbreweriesに登録されているかチェック
            if url:
                check = supabase.table('breweries').select('id').eq('untappd_url', url).execute()
                if check.data:
                    print(f"     → ✅ breweries テーブルに登録済み")
                else:
                    print(f"     → ❌ breweries テーブルに未登録")
            print()
    else:
        print(f"  ❌ untappd_data テーブルに '{brewery_name}' のビールは見つかりません")
    
    print("=" * 80)

if __name__ == "__main__":
    search_brewery("Future Brewing")

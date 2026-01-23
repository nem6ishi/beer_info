#!/usr/bin/env python3
"""
特定の商品の is_set フラグを修正
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db import get_supabase_client

def fix_glass_is_set():
    supabase = get_supabase_client()
    
    print("🔧 カンティヨン専用グラスの is_set フラグを修正中...")
    print("=" * 80)
    
    # カンティヨン専用グラスを検索
    res = supabase.from_('scraped_beers') \
        .select('url, name') \
        .ilike('name', '%カンティヨン専用グラス%') \
        .execute()
    
    if not res.data:
        print("❌ カンティヨン専用グラスが見つかりません")
        return
    
    for item in res.data:
        url = item['url']
        name = item['name']
        print(f"\n  商品: {name}")
        print(f"  URL: {url}")
        
        # gemini_data の is_set を False に更新
        try:
            update_res = supabase.table('gemini_data') \
                .update({'is_set': False}) \
                .eq('url', url) \
                .execute()
            
            print(f"  ✅ is_set を False に更新しました")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
    
    print("\n" + "=" * 80)
    print("完了！")

if __name__ == "__main__":
    fix_glass_is_set()

#!/usr/bin/env python3
"""
Untappd enrichment の失敗データを確認
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db import get_supabase_client
from collections import Counter

def check_failures():
    supabase = get_supabase_client()
    
    print("=" * 80)
    print("🔍 Untappd Enrichment 失敗データの確認")
    print("=" * 80)
    
    # 未解決の失敗データを取得
    print("\n📊 未解決の失敗を取得中...")
    failures_res = supabase.table('untappd_search_failures') \
        .select('*') \
        .eq('resolved', False) \
        .order('last_failed_at', desc=True) \
        .execute()
    
    failures = failures_res.data
    
    if not failures:
        print("\n✅ 未解決の失敗はありません！")
        return
    
    print(f"\n⚠️  未解決の失敗: {len(failures)} 件")
    
    # 失敗理由の集計
    reasons = Counter(f.get('failure_reason') for f in failures)
    
    print("\n📈 失敗理由の内訳:")
    print("-" * 80)
    for reason, count in reasons.most_common():
        print(f"  {reason}: {count} 件")
    
    # 失敗商品の一覧表示
    print(f"\n📋 失敗した商品一覧（全{len(failures)}件）:")
    print("-" * 80)
    
    for i, failure in enumerate(failures, 1):
        beer = failure.get('beer_name', 'Unknown')
        brewery = failure.get('brewery_name', 'Unknown')
        beer_jp = failure.get('beer_name_jp', '')
        
        # 日本語名がある場合は追加表示
        if beer_jp and beer_jp != beer:
            print(f"{i}. {beer} ({beer_jp}) / {brewery}")
        else:
            print(f"{i}. {beer} / {brewery}")
    
    print("\n" + "=" * 80)
    
    return failures

if __name__ == "__main__":
    failures = check_failures()

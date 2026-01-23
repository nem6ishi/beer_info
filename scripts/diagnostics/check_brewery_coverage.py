#!/usr/bin/env python3
"""
診断スクリプト: Untappd enrichment 済みビールのブルワリー登録状況を確認
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db import get_supabase_client

def check_brewery_coverage():
    supabase = get_supabase_client()
    
    print("=" * 80)
    print("🔍 ブルワリー登録状況チェック")
    print("=" * 80)
    
    # 1. untappd_data から一意のブルワリーURLを取得
    print("\n📊 Step 1: untappd_data テーブルのブルワリーURL収集中...")
    untappd_res = supabase.table('untappd_data') \
        .select('untappd_brewery_url, brewery_name') \
        .not_.is_('untappd_brewery_url', 'null') \
        .execute()
    
    unique_brewery_urls = {}
    for item in untappd_res.data:
        url = item.get('untappd_brewery_url')
        name = item.get('brewery_name')
        if url:
            unique_brewery_urls[url] = name
    
    print(f"   ✅ untappd_data 内の一意のブルワリーURL数: {len(unique_brewery_urls)}")
    
    # 2. breweries テーブルに登録されているかチェック
    print("\n📊 Step 2: breweries テーブルの登録状況確認中...")
    breweries_res = supabase.table('breweries') \
        .select('untappd_url, name_en, logo_url') \
        .execute()
    
    registered_urls = {b['untappd_url'] for b in breweries_res.data}
    print(f"   ✅ breweries テーブル内のブルワリー数: {len(registered_urls)}")
    
    # 3. 未登録のブルワリーURLを特定
    missing_urls = set(unique_brewery_urls.keys()) - registered_urls
    
    print("\n" + "=" * 80)
    print("📈 結果サマリー")
    print("=" * 80)
    print(f"Untappd enrichment 済みビールのブルワリー数: {len(unique_brewery_urls)}")
    print(f"breweries テーブルに登録済み: {len(registered_urls)}")
    print(f"未登録のブルワリー: {len(missing_urls)}")
    print(f"登録率: {len(registered_urls) / len(unique_brewery_urls) * 100:.1f}%")
    
    # 4. 未登録ブルワリーの詳細表示
    if missing_urls:
        print("\n⚠️  未登録のブルワリー:")
        print("-" * 80)
        for i, url in enumerate(sorted(missing_urls)[:20], 1):
            name = unique_brewery_urls.get(url, 'Unknown')
            print(f"  {i}. {name}")
            print(f"     URL: {url}")
        
        if len(missing_urls) > 20:
            print(f"\n  ... 他 {len(missing_urls) - 20} 件")
    else:
        print("\n✅ 全てのブルワリーが breweries テーブルに登録されています！")
    
    # 5. logo_url が設定されているブルワリー数
    breweries_with_logo = sum(1 for b in breweries_res.data if b.get('logo_url'))
    print(f"\n📸 ロゴ画像設定済み: {breweries_with_logo} / {len(breweries_res.data)} ({breweries_with_logo / len(breweries_res.data) * 100:.1f}%)")
    
    print("\n" + "=" * 80)
    
    return {
        'total_breweries': len(unique_brewery_urls),
        'registered': len(registered_urls),
        'missing': len(missing_urls),
        'missing_urls': list(missing_urls)
    }

if __name__ == "__main__":
    result = check_brewery_coverage()
    
    # 未登録がある場合は終了コード1
    sys.exit(0 if result['missing'] == 0 else 1)

#!/usr/bin/env python
"""特定のアローム商品名を修正するスクリプト"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import get_supabase_client
from src.scrapers.arome import fetch_full_name

# 修正するURL
URLS_TO_FIX = [
    "https://www.arome.jp/products/detail.php?product_id=5725",
    "https://www.arome.jp/products/detail.php?product_id=5724",
]

def main():
    client = get_supabase_client()
    
    print("特定の商品名を修正します\n")
    
    for url in URLS_TO_FIX:
        # 現在の名前を取得
        result = client.table('scraped_beers').select('name').eq('url', url).execute()
        
        if not result.data:
            print(f"✗ 商品が見つかりません: {url}")
            continue
        
        old_name = result.data[0]['name']
        print(f"\n現在: {old_name}")
        print(f"URL: {url}")
        
        # 詳細ページから完全な名前を取得
        full_name = fetch_full_name(url)
        
        if full_name and full_name != old_name:
            print(f"新規: {full_name}")
            
            try:
                client.table('scraped_beers').update({'name': full_name}).eq('url', url).execute()
                print("✓ 更新成功")
            except Exception as e:
                print(f"✗ 更新失敗: {e}")
        elif full_name:
            print("- 変更なし（同じ名前）")
        else:
            print("✗ 取得失敗")

if __name__ == '__main__':
    main()

#!/usr/bin/env python
"""アロームの切れた商品名を修正するスクリプト"""
import sys
from pathlib import Path
import time

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import get_supabase_client
from src.scrapers.arome import fetch_full_name

def main():
    client = get_supabase_client()
    
    # 名前が "..." または "…" または ".." で終わるアローム商品を検索
    print("切れた商品名を検索中...\n")
    
    result = client.table('scraped_beers').select('url, name').eq('shop', 'アローム').execute()
    
    print(f"アロームの全商品数: {len(result.data)}\n")
    
    truncated_items = []
    for item in result.data:
        name = item.get('name', '')
        # より広い範囲で切れた名前を検出
        ends_with_dots = name.endswith('...') or name.endswith('…') or name.endswith('..')
        if ends_with_dots:
            print(f"  検出: ...{name[-40:]}")
            truncated_items.append(item)
    
    print(f"\n見つかった切れた商品名: {len(truncated_items)} 件\n")
    
    if not truncated_items:
        print("修正が必要な商品はありません。")
        return
    
    # 確認
    print("以下の商品名を修正します:")
    for i, item in enumerate(truncated_items[:10], 1):
        print(f"{i:2d}. {item['name']}")
    if len(truncated_items) > 10:
        print(f"    ... 他 {len(truncated_items) - 10} 件")
    
    print()
    
    # 修正実行
    updated_count = 0
    failed_count = 0
    
    for i, item in enumerate(truncated_items, 1):
        url = item['url']
        old_name = item['name']
        
        print(f"[{i}/{len(truncated_items)}] 取得中: {url}")
        
        full_name = fetch_full_name(url)
        
        if full_name and full_name != old_name:
            # 更新
            try:
                client.table('scraped_beers').update({'name': full_name}).eq('url', url).execute()
                print(f"  ✓ 更新: {full_name}")
                updated_count += 1
            except Exception as e:
                print(f"  ✗ 更新失敗: {e}")
                failed_count += 1
        elif full_name:
            print(f"  - 変更なし")
        else:
            print(f"  ✗ 取得失敗")
            failed_count += 1
        
        # レート制限対策
        if i < len(truncated_items):
            time.sleep(0.5)
    
    print(f"\n{'='*60}")
    print(f"完了:")
    print(f"  更新: {updated_count} 件")
    print(f"  失敗: {failed_count} 件")
    print(f"  合計: {len(truncated_items)} 件")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()

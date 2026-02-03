#!/usr/bin/env python
"""全ショップの商品名パターンを確認するスクリプト"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import get_supabase_client

def main():
    client = get_supabase_client()
    
    # 全ショップのリストを取得し、件数もカウント
    shops_result = client.table('scraped_beers').select('shop').execute()
    shop_counts = {}
    for item in shops_result.data:
        shop = item['shop']
        shop_counts[shop] = shop_counts.get(shop, 0) + 1
    
    print(f"総ショップ数: {len(shop_counts)}")
    print(f"総商品数: {sum(shop_counts.values())}\n")
    
    # ショップごとの件数を表示
    for shop in sorted(shop_counts.keys()):
        print(f"  {shop}: {shop_counts[shop]} 件")
    
    print("\n" + "=" * 80)
    
    for shop in sorted(shop_counts.keys()):
        print(f"\n【{shop}】 ({shop_counts[shop]} 件)")
        print("-" * 80)
        
        # 各ショップの商品を20件取得
        result = client.table('scraped_beers').select('name').eq('shop', shop).limit(20).execute()
        
        print(f"サンプル表示: {min(15, len(result.data))} 件\n")
        
        for i, product in enumerate(result.data[:15], 1):  # 最大15件表示
            print(f"{i:2d}. {product.get('name', 'N/A')}")
        
        if len(result.data) > 15:
            print(f"    ... (他 {len(result.data) - 15} 件)")
        
        print()

if __name__ == '__main__':
    main()

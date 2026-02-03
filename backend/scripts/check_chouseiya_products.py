#!/usr/bin/env python
"""ちょうせいやの商品名を確認するスクリプト"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import get_supabase_client

def main():
    client = get_supabase_client()
    
    # ちょうせいやの商品を取得
    result = client.table('scraped_beers').select('*').eq('shop', 'ちょうせいや').limit(50).execute()
    
    print(f"ちょうせいやの商品数（最大50件表示）: {len(result.data)}\n")
    
    for product in result.data:
        print(f"商品名: {product.get('name', 'N/A')}")
        print(f"  URL: {product.get('url', 'N/A')}")
        if 'beer_name' in product:
            print(f"  Beer: {product.get('beer_name')}")
        if 'brewery_name' in product:
            print(f"  Brewery: {product.get('brewery_name')}")
        print()

if __name__ == '__main__':
    main()

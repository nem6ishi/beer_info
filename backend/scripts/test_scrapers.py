#!/usr/bin/env python
"""各スクレイパーのサンプル実行スクリプト"""
import asyncio
import json
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers import beervolta, chouseiya, ichigo_ichie, arome

async def main():
    print("=" * 80)
    print("各ショップの商品名サンプル取得")
    print("=" * 80)
    
    # BEER VOLTA
    print("\n【BEER VOLTA】")
    print("-" * 80)
    try:
        volta_data = await beervolta.scrape_beervolta(limit=10)
        for i, item in enumerate(volta_data[:10], 1):
            print(f"{i:2d}. {item['name']}")
    except Exception as e:
        print(f"Error: {e}")
    
    # ちょうせいや
    print("\n【ちょうせいや】")
    print("-" * 80)
    try:
        chouseiya_data = await chouseiya.scrape_chouseiya(limit=10)
        for i, item in enumerate(chouseiya_data[:10], 1):
            print(f"{i:2d}. {item['name']}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 一期一会～る
    print("\n【一期一会～る】")
    print("-" * 80)
    try:
        ichigo_data = await ichigo_ichie.scrape_ichigo_ichie(limit=10)
        for i, item in enumerate(ichigo_data[:10], 1):
            print(f"{i:2d}. {item['name']}")
    except Exception as e:
        print(f"Error: {e}")
    
    # アローム
    print("\n【アローム】")
    print("-" * 80)
    try:
        arome_data = await arome.scrape_arome(limit=10)
        for i, item in enumerate(arome_data[:10], 1):
            print(f"{i:2d}. {item['name']}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    asyncio.run(main())

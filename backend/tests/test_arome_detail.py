#!/usr/bin/env python
"""アロームの詳細ページから完全な商品名を取得するテスト"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.arome import fetch_full_name

# 問題のURL
url = "https://www.arome.jp/products/detail.php?product_id=5725"

print(f"URL: {url}\n")
print("詳細ページから商品名を取得中...\n")

full_name = fetch_full_name(url)

if full_name:
    print(f"✓ 取得成功:")
    print(f"  {full_name}")
else:
    print("✗ 取得失敗")

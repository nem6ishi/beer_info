#!/usr/bin/env python
"""醸造所名検証ロジックのテスト"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.untappd.searcher import clean_brewery_name, normalize_for_comparison

# テストケース
result_brewery = "Vinohradský pivovar"
expected_brewery = "Vinohradský"

print("=" * 60)
print("醸造所名検証テスト")
print("=" * 60)

print(f"\n結果の醸造所名: {result_brewery}")
print(f"期待される醸造所名: {expected_brewery}")

# 1. 正規化チェック
rb_norm = normalize_for_comparison(result_brewery)
eb_norm = normalize_for_comparison(expected_brewery)

print(f"\n1. 正規化チェック:")
print(f"   結果 (正規化): '{rb_norm}'")
print(f"   期待 (正規化): '{eb_norm}'")
print(f"   一致: {rb_norm in eb_norm or eb_norm in rb_norm}")

# 2. クリーニングチェック
cleaned_result = clean_brewery_name(result_brewery)
cleaned_expected = clean_brewery_name(expected_brewery)
cr_norm = normalize_for_comparison(cleaned_result)
ce_norm = normalize_for_comparison(cleaned_expected)

print(f"\n2. クリーニングチェック:")
print(f"   結果 (クリーニング): '{cleaned_result}'")
print(f"   期待 (クリーニング): '{cleaned_expected}'")
print(f"   結果 (クリーニング+正規化): '{cr_norm}'")
print(f"   期待 (クリーニング+正規化): '{ce_norm}'")
print(f"   一致: {cr_norm and ce_norm and (cr_norm in ce_norm or ce_norm in cr_norm)}")

print(f"\n{'=' * 60}")
print("結論:")
if cr_norm and ce_norm and (cr_norm in ce_norm or ce_norm in cr_norm):
    print("✓ クリーニングチェックで一致します！")
elif rb_norm in eb_norm or eb_norm in rb_norm:
    print("✓ 正規化チェックで一致します！")
else:
    print("✗ 一致しません")
print(f"{'=' * 60}")

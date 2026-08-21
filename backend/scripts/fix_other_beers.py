#!/usr/bin/env python3
"""
gemini_data テーブル内で product_type = 'other' と誤分類されている
ビール・飲料商品を検知・判定し、product_type = 'beer' に修正更新するスクリプト。
"""
import re
import logging
from typing import List, Dict, Any
from backend.src.core.db import get_supabase_client, refresh_materialized_view

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fix_other_beers")

NON_BEVERAGE_PATTERN = re.compile(
    r'(書籍|単行本|新書|文庫|著者|出版|雑誌|ZINE|ガイドライン|テイスティングノート|解体新書|Tシャツ|トートバッグ|グラス|ステッカー|コースター|キーホルダー|服飾|冊子|Zine|論考集|業界俯瞰図|二日酔い|防ぎ方|治し方|教本|カタログ)',
    re.IGNORECASE
)

def fix_other_beers():
    supabase = get_supabase_client()
    logger.info("🔍 gemini_data 内の product_type = 'other' のアイテムをチェック中...")

    res = supabase.table("gemini_data").select("*").eq("product_type", "other").execute()
    items = res.data or []
    logger.info(f"対象総数: {len(items)}件")

    corrected_count = 0

    for r in items:
        url_val = r.get("url", "")
        # fetch scraped_beers title
        sb = supabase.table("scraped_beers").select("name, shop").eq("url", url_val).execute()
        title = sb.data[0]["name"] if sb.data else ""
        shop = sb.data[0]["shop"] if sb.data else ""

        # Skip if title explicitly indicates non-beverage merchandise
        if title and NON_BEVERAGE_PATTERN.search(title):
            logger.info(f"  ⏩ 保持 (非飲料グッズ): [{shop}] {title}")
            continue

        b_en = r.get("brewery_name_en") or ""
        b_jp = r.get("brewery_name_jp") or ""
        beer_en = r.get("beer_name_en") or ""
        beer_jp = r.get("beer_name_jp") or ""

        # Check if valid names or title indicate a beer
        has_name = (b_en and b_en.lower() != "none") or (b_jp and b_jp.lower() != "none") or (beer_en and beer_en.lower() != "none") or (beer_jp and beer_jp.lower() != "none")
        if has_name or title:
            is_set = r.get("is_set", False)
            target_type = "set" if is_set else "beer"

            logger.info(f"  ✨ 修正対象: [{shop}] {title or url_val} -> product_type: '{target_type}'")
            try:
                supabase.table("gemini_data").update({"product_type": target_type}).eq("url", url_val).execute()
                corrected_count += 1
            except Exception as e:
                logger.error(f"  ❌ 更新エラー ({url_val}): {e}")

    logger.info(f"🏁 修正完了: {corrected_count}件の gemini_data レコードを更新しました。")

    if corrected_count > 0:
        refresh_materialized_view(supabase, logger)

if __name__ == "__main__":
    fix_other_beers()

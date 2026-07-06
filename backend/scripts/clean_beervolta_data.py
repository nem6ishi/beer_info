#!/usr/bin/env python3
"""
BEER VOLTA の商品名（scraped_beers, gemini_data）から
「≪7/4入荷予定≫」などの不要な入荷予定・セール・予約文字列を除去し、
 Untappd検索失敗履歴（untappd_search_failures）をリセットするスクリプト。
"""
import asyncio
import re
import logging
from typing import List, Dict, Any
from backend.src.core.db import get_supabase_client, refresh_materialized_view

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clean_beervolta")

def clean_name(name: str) -> str:
    if not name:
        return ""
    # 括弧テキスト除去
    cleaned = re.sub(r'[≪《<＜【\[].*?(?:入荷|予約|予定|出荷|空輸|クール|SALE|売切|新着).*?[≫》>＞\]】]', '', name, flags=re.IGNORECASE)
    indicators = ['≪入荷予定≫', '《入荷予定》', '≪予約≫', '《予約》', '売切', 'SOLD OUT', 'SALE!!', 'SALE!']
    for ind in indicators:
        cleaned = re.sub(re.escape(ind), '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'[0-9,]+円.*', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def fetch_all(supabase: Any, table: str, shop_filter: bool = False, url_filter: bool = False) -> List[Dict[str, Any]]:
    all_data = []
    offset = 0
    limit = 1000
    while True:
        query = supabase.table(table).select("*")
        if shop_filter:
            query = query.eq("shop", "BEER VOLTA")
        if url_filter:
            query = query.ilike("url", "%beervolta.com%")
        res = query.limit(limit).offset(offset).execute()
        data = res.data or []
        all_data.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_data

async def main():
    supabase = get_supabase_client()
    logger.info("🚀 BEER VOLTA のデータクリーンアップ開始...")

    # 1. scraped_beers のクリーンアップ
    logger.info("📦 1. scraped_beers のチェック...")
    scraped_items = fetch_all(supabase, "scraped_beers", shop_filter=True)
    logger.info(f"  対象総数: {len(scraped_items)}件")

    scraped_updates = 0
    for item in scraped_items:
        original_name = item.get("name", "")
        cleaned = clean_name(original_name)
        if cleaned and cleaned != original_name:
            try:
                supabase.table("scraped_beers").update({"name": cleaned}).eq("url", item["url"]).execute()
                scraped_updates += 1
            except Exception as e:
                logger.error(f"  ❌ scraped_beers 更新エラー ({item['url']}): {e}")

    logger.info(f"  ✨ scraped_beers 更新完了: {scraped_updates}件変更")

    # 2. gemini_data のクリーンアップ
    logger.info("🤖 2. gemini_data のチェック...")
    gemini_items = fetch_all(supabase, "gemini_data", url_filter=True)
    logger.info(f"  対象総数: {len(gemini_items)}件")

    gemini_updates = 0
    for g_item in gemini_items:
        changed = False
        update_payload = {}
        for field in ["beer_name_en", "beer_name_jp", "beer_name_core"]:
            val = g_item.get(field)
            if val:
                cleaned_val = clean_name(val)
                if cleaned_val and cleaned_val != val:
                    update_payload[field] = cleaned_val
                    changed = True
        
        # search_hint も同様に再構成・クリーニング
        hint = g_item.get("search_hint")
        if hint:
            cleaned_hint = clean_name(hint)
            if cleaned_hint != hint:
                update_payload["search_hint"] = cleaned_hint
                changed = True

        if changed:
            try:
                supabase.table("gemini_data").update(update_payload).eq("url", g_item["url"]).execute()
                gemini_updates += 1
            except Exception as e:
                logger.error(f"  ❌ gemini_data 更新エラー ({g_item['url']}): {e}")

    logger.info(f"  ✨ gemini_data 更新完了: {gemini_updates}件変更")

    # 3. untappd_search_failures のリセット
    logger.info("🔄 3. untappd_search_failures のリセット...")
    try:
        res_fail = supabase.table("untappd_search_failures") \
            .update({"resolved": True}) \
            .ilike("product_url", "%beervolta.com%") \
            .eq("resolved", False) \
            .execute()
        failures_reset = len(res_fail.data) if res_fail.data else 0
        logger.info(f"  ✨ untappd_search_failures リセット完了: {failures_reset}件を解決済みに変更")
    except Exception as e:
        logger.error(f"  ❌ untappd_search_failures リセットエラー: {e}")

    # 4. マテリアライズドビューの更新
    refresh_materialized_view(supabase, logger)
    logger.info("🏁 すべてのクリーンアップが完了しました！")

if __name__ == "__main__":
    asyncio.run(main())

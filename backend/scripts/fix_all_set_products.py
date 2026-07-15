#!/usr/bin/env python3
"""
本番DBの全商品データを点検し、「〜本セット」「Cans Set」「飲み比べ」などの明確なセット商品キーワードが
タイトル (scraped_beers.name) に含まれているにもかかわらず、gemini_data テーブル上で is_set=False や
product_type='beer' となってしまっている既存レコードをすべて検出して自動補正・UPDATEする一括バッチスクリプト。
"""

import re
import sys
import logging
from typing import List, Dict, Any, cast
from datetime import datetime, timezone

from dotenv import load_dotenv
from backend.src.core.db import get_supabase_client, sync_execute, refresh_materialized_view

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# セット商品キーワードの確定的正規表現（〜本セット等のみ限定し、購入条件「5本以上注文必須」等は除外）
SET_PATTERN = re.compile(
    r'(\d+本(?:パック|セット|アソート|飲み比べ)|\d+\s*Cans?\s*(?:Set|Pack)|\d+\s*Bottles?\s*(?:Set|Pack)|飲み比べ|アソート|お試しセット|本セット|缶セット|Variety\s*Pack)',
    re.IGNORECASE
)

def fetch_all_rows(sb, table_name, select_cols) -> List[Dict[str, Any]]:
    all_data = []
    offset = 0
    limit = 1000
    while True:
        res = sync_execute(sb.table(table_name).select(select_cols).range(offset, offset + limit - 1))
        rows = res.data or []
        all_data.extend(rows)
        if len(rows) < limit:
            break
        offset += limit
    return all_data

def fix_all_set_products():
    load_dotenv()
    sb = get_supabase_client()
    
    logger.info("🔍 本番DBの全商品をスキャンし、セット商品の判定チェックとクリーンアップを開始します...")
    
    # 0. 先ほど誤って広すぎるパターンで登録された非セット商品（単なる購入条件）のクリーンアップ
    logger.info("🧹 誤判定された RESOLVED_BY_SET_KEYWORD_RULE の点検とクリーンアップ中...")
    all_g_items = fetch_all_rows(sb, 'gemini_data', 'url, payload')
    
    deleted_count = 0
    for item in all_g_items:
        payload_str = str(item.get('payload', ''))
        if 'RESOLVED_BY_SET_KEYWORD_RULE:' in payload_str:
            title = payload_str.replace('RESOLVED_BY_SET_KEYWORD_RULE: ', '')
            # 厳格なパターンに一致しないものは削除
            if not SET_PATTERN.search(title):
                logger.info(f"  🗑️ [削除（購入条件の誤検知クリーンアップ）] {title[:45]}...")
                sync_execute(sb.table('gemini_data').delete().eq('url', item['url']))
                deleted_count += 1
            
    logger.info(f"✅ 誤検知クリーンアップ完了: {deleted_count} 件削除")

    
    # 1. scraped_beers から全URLとタイトルを取得
    logger.info("📦 scraped_beers テーブルを全件取得中...")
    scraped_items = fetch_all_rows(sb, 'scraped_beers', 'url, name')
    logger.info(f"👉 scraped_beers 総件数: {len(scraped_items)}")


    logger.info(f"👉 scraped_beers 総件数: {len(scraped_items)}")
    
    # URL -> title のマップと、タイトルから見たセット対象URLのセットを作成
    url_to_title = {item['url']: item['name'] for item in scraped_items if item.get('url') and item.get('name')}
    set_urls = set()
    for url, title in url_to_title.items():
        if SET_PATTERN.search(title):
            set_urls.add(url)
            
    logger.info(f"✅ タイトルから「確実なセット商品」と判定された総件数: {len(set_urls)} 件")
    
    # 2. gemini_data から現在の状況を取得
    logger.info("📦 gemini_data テーブルを全件取得中...")
    gemini_items = fetch_all_rows(sb, 'gemini_data', 'url, brewery_name_en, brewery_name_jp, beer_name_en, beer_name_jp, beer_name_core, search_hint, is_set, product_type, untappd_url, payload')
    logger.info(f"👉 gemini_data 総件数: {len(gemini_items)}")

    
    # 既存 gemini_data の中での要修正リスト（is_set が True でない、または product_type が 'set' でない）
    to_update_list = []
    gemini_urls = set()
    
    for item in gemini_items:
        url = item['url']
        gemini_urls.add(url)
        if url in set_urls:
            is_set = item.get('is_set')
            prod_type = item.get('product_type')
            
            if not is_set or prod_type != 'set':
                title = url_to_title.get(url, '')
                logger.info(f"  ⚠️ [要補正（既存データ誤判定）] {title}")
                logger.info(f"     URL: {url} | 現在: is_set={is_set}, product_type='{prod_type}'")
                
                # UPDATE用ペイロード作成
                upd = item.copy()
                upd['is_set'] = True
                upd['product_type'] = 'set'
                upd['updated_at'] = datetime.now(timezone.utc).isoformat()
                
                to_update_list.append(upd)
                
    # 3. タイトルがセット商品なのに、まだ gemini_data にすら入っていない（未推論）商品の新規作成
    to_insert_list = []
    for url in set_urls:
        if url not in gemini_urls:
            title = url_to_title.get(url, '')
            logger.info(f"  ⚠️ [要登録（未Enrichセット商品）] {title}")
            to_insert_list.append({
                'url': url,
                'is_set': True,
                'product_type': 'set',
                'payload': f'RESOLVED_BY_SET_KEYWORD_RULE: {title}',
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            
    total_targets = len(to_update_list) + len(to_insert_list)
    logger.info(f"\n📊 --- スキャン結果サマリー ---")
    logger.info(f"既存データの誤判定・要アップデート件数: {len(to_update_list)} 件")
    logger.info(f"未登録の確定的セット商品の新規登録件数: {len(to_insert_list)} 件")
    logger.info(f"合計補正対象: {total_targets} 件\n")
    
    if total_targets == 0:
        logger.info("✨ 補正が必要なデータはありませんでした！")
        return

    # 4. バッチ更新・登録の実行
    logger.info("💾 gemini_data テーブルへの一括補正・保存を実行中...")
    
    # UPDATE実行
    if to_update_list:
        # 100件ずつのバッチで upsert
        for i in range(0, len(to_update_list), 100):
            batch = to_update_list[i:i+100]
            sync_execute(sb.table('gemini_data').upsert(batch))
        logger.info(f"  ✅ {len(to_update_list)} 件の既存データを 'set' 扱いに上書き完了！")
        
    # INSERT実行
    if to_insert_list:
        for i in range(0, len(to_insert_list), 100):
            batch = to_insert_list[i:i+100]
            sync_execute(sb.table('gemini_data').upsert(batch))
        logger.info(f"  ✅ {len(to_insert_list)} 件の未登録セット商品を 'set' 扱いで新規登録完了！")
        
    # 5. マテリアライズドビューのリフレッシュ
    logger.info("\n🔄 本番のマテリアライズドビュー (beer_info_view) を最新化しています...")
    refresh_materialized_view(sb, logger)
    logger.info("✨ すべての補正と本番反映が完了しました！")

if __name__ == '__main__':
    fix_all_set_products()

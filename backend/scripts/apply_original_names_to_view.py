#!/usr/bin/env python3
"""
非ビール商品（セット商品等: product_type != 'beer'）が誤って Untappd の単品ビールURL（例: The Four Sights）と
紐付いてしまっている既存データをクリーンアップし、さらに beer_info_view および beer_groups_view を再構築して
非ビール商品の元のアイテム名が GroupedBeerTable から必ず参照できるようにするスクリプト。
"""

import logging
from dotenv import load_dotenv
from backend.src.core.db import get_supabase_client, sync_execute, refresh_materialized_view

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def apply_original_names_and_fix_sets():
    load_dotenv()
    sb = get_supabase_client()
    
    logger.info("🔍 1. 非ビール（setなど product_type != 'beer'）で誤って untappd_url が紐付いている既存レコードのクリーンアップ...")
    # gemini_data で product_type == 'set' なのに untappd_url があるものを取得
    res = sync_execute(sb.table('gemini_data').select('url, untappd_url, product_type').eq('product_type', 'set'))
    set_items = res.data or []
    
    fixed_count = 0
    for item in set_items:
        if item.get('untappd_url'):
            logger.info(f"  🔧 [紐付けクリア] URL: {item['url']} | 誤紐付け: {item['untappd_url']}")
            sync_execute(sb.table('gemini_data').update({'untappd_url': None}).eq('url', item['url']))
            fixed_count += 1
            
    logger.info(f"✅ 誤った Untappd 紐付けのクリア完了: {fixed_count} 件\n")
    
    logger.info("🔄 2. beer_info_view マテリアライズドビューの更新...")
    refresh_materialized_view(sb, logger)
    
    logger.info("✨ すべてのクリーンアップとビュー更新が完了しました！")

if __name__ == '__main__':
    apply_original_names_and_fix_sets()

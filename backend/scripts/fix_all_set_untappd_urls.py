#!/usr/bin/env python3
"""
scraped_beers テーブルおよび gemini_data テーブルにおいて、
セット商品（product_type = 'set'、is_set = True、あるいは商品名に '本セット' / 'Cans Set' 等を含むもの）に
誤って設定されてしまっている単品ビールの untappd_url（例: The Four Sights, Shred IPA など）をすべて NULL に是正・クリアし、
beer_info_view マテリアライズドビューをリフレッシュするスクリプト。
"""

import logging
import re
from dotenv import load_dotenv
from backend.src.core.db import get_supabase_client, sync_execute, refresh_materialized_view

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def clean_all_set_untappd_urls():
    load_dotenv()
    sb = get_supabase_client()
    
    # 判定用正規表現
    set_pattern = re.compile(
        r'(?:(?:\d+|[一二三四五六七八九十百]+)\s*[\-〜~～]?\s*(?:\d+|[一二三四五六七八九十百]+)?\s*(?:本|缶|種|種類|個|パック)\s*(?:セット|set|パック|入)|'
        r'(?:\d+|[一二三四五六七八九十百]+)\s*(?:cans?|bottles?|packs?)\s*set|'
        r'飲み比べ|テイスティングセット|tasting\s*set|box\s*set|gift\s*set|'
        r'福袋|お試し(?:セット|パック)|コンプリート(?:セット|パック)|アソート|バラエティ)',
        re.IGNORECASE
    )
    
    # 除外（購入条件など）
    exclude_pattern = re.compile(
        r'(?:[456789\d]+本(?:以上)?(?:の)?(?:ご注文|購入|注文)|ご注文は|\b以上\b|最大|まで|制限|必須|送料|お一人様|1アカウント|合算)',
        re.IGNORECASE
    )

    logger.info("🔍 1. scraped_beers テーブルから untappd_url が設定されている全レコードをスキャン...")
    res = sync_execute(sb.table('scraped_beers').select('url, name, untappd_url').neq('untappd_url', 'null'))
    scraped_items = res.data or []
    
    scraped_fixed = 0
    for item in scraped_items:
        name = item.get('name', '')
        u_url = item.get('untappd_url')
        if not u_url:
            continue
        
        # セットかどうかの判定
        if set_pattern.search(name) and not exclude_pattern.search(name):
            logger.info(f"  🛑 [scraped_beersクリア] URL: {item['url']}")
            logger.info(f"      商品名: {name}")
            logger.info(f"      誤紐付け: {u_url}")
            sync_execute(sb.table('scraped_beers').update({'untappd_url': None}).eq('url', item['url']))
            scraped_fixed += 1

    logger.info(f"✅ scraped_beers の是正完了: {scraped_fixed} 件\n")

    logger.info("🔍 2. gemini_data テーブルから、product_type = 'set' 又は is_set = True なのに untappd_url があるものをクリア...")
    res_g = sync_execute(sb.table('gemini_data').select('url, untappd_url, product_type, is_set').or_('product_type.eq.set,is_set.eq.true'))
    gemini_items = res_g.data or []
    
    gemini_fixed = 0
    for item in gemini_items:
        u_url = item.get('untappd_url')
        if u_url:
            logger.info(f"  🛑 [gemini_dataクリア] URL: {item['url']} | 誤紐付け: {u_url}")
            sync_execute(sb.table('gemini_data').update({'untappd_url': None}).eq('url', item['url']))
            gemini_fixed += 1

    logger.info(f"✅ gemini_data の是正完了: {gemini_fixed} 件\n")

    logger.info("🔄 3. マテリアライズドビュー (beer_info_view) のリフレッシュ...")
    refresh_materialized_view(sb, logger)
    logger.info("✨ すべてのクリーンアップ＆ビュー更新が完了しました！")

if __name__ == '__main__':
    clean_all_set_untappd_urls()

#!/usr/bin/env python
"""Untappd詳細をスクレイピングして保存するスクリプト"""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import get_supabase_client
from src.services.untappd.searcher import scrape_beer_details

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def scrape_and_save_details(untappd_url: str):
    """Untappd URLから詳細をスクレイピングして保存"""
    logger.info(f"🔄 スクレイピング: {untappd_url}")
    
    # レート制限
    await asyncio.sleep(2)
    
    details = scrape_beer_details(untappd_url)
    
    if not details:
        logger.error("❌ 詳細のスクレイピングに失敗しました")
        return False
    
    logger.info(f"✓ 詳細取得成功:")
    logger.info(f"  ビール名: {details.get('untappd_beer_name')}")
    logger.info(f"  醸造所: {details.get('untappd_brewery_name')}")
    logger.info(f"  スタイル: {details.get('untappd_style')}")
    logger.info(f"  評価: {details.get('untappd_rating')} ({details.get('untappd_rating_count')} ratings)")
    logger.info(f"  ABV: {details.get('untappd_abv')}%")
    logger.info(f"  IBU: {details.get('untappd_ibu')}")
    
    # untappd_dataに保存
    logger.info("\n💾 Untappd詳細を保存中...")
    supabase = get_supabase_client()
    
    untappd_payload = {
        'untappd_url': untappd_url,
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': details.get('untappd_brewery_name'),
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'ibu': details.get('untappd_ibu'),
        'rating': details.get('untappd_rating'),
        'rating_count': details.get('untappd_rating_count'),
        'image_url': details.get('untappd_label'),
        'untappd_brewery_url': details.get('untappd_brewery_url'),
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }
    
    supabase.table('untappd_data').upsert(untappd_payload).execute()
    logger.info("✓ 詳細保存完了")
    return True

async def main():
    untappd_url = "https://untappd.com/b/vinohradsky-pivovar-vinohradska-12-non-alcoholic/6580130"
    await scrape_and_save_details(untappd_url)

if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python
"""特定のURLをエンリッチするスクリプト"""
import asyncio
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import get_supabase_client
from src.services.gemini.extractor import GeminiExtractor
from src.services.store.brewery_manager import BreweryManager
from src.services.untappd.searcher import get_untappd_url

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

async def enrich_specific_url(url: str):
    """特定のURLをGeminiとUntappdでエンリッチ"""
    
    logger.info("=" * 70)
    logger.info(f"🔄 エンリッチ対象: {url}")
    logger.info("=" * 70)
    
    # データベースとサービスの初期化
    supabase = get_supabase_client()
    extractor = GeminiExtractor()
    brewery_manager = BreweryManager()
    
    # 商品情報を取得
    logger.info("\n📂 商品情報を取得中...")
    result = supabase.table('beer_info_view').select('*').eq('url', url).execute()
    
    if not result.data:
        logger.error(f"❌ URLが見つかりません: {url}")
        return
    
    beer = result.data[0]
    logger.info(f"✓ 商品名: {beer['name']}")
    logger.info(f"  ショップ: {beer.get('shop', 'Unknown')}")
    
    # Geminiエンリッチメント
    logger.info("\n🤖 Geminiでビール情報を抽出中...")
    
    # 既知の醸造所をヒントとして使用
    known_brewery = None
    matches = brewery_manager.find_breweries_in_text(beer['name'])
    if matches:
        known_brewery = ", ".join([b['name_en'] for b in matches])
        logger.info(f"  🏭 既知の醸造所ヒント: {known_brewery}")
    
    enriched_info = await extractor.extract_info(
        beer['name'], 
        known_brewery=known_brewery, 
        shop=beer.get('shop')
    )
    
    if not enriched_info:
        logger.error("❌ Geminiから情報を取得できませんでした")
        return
    
    logger.info(f"\n✓ 抽出結果:")
    logger.info(f"  醸造所 (EN): {enriched_info.get('brewery_name_en')}")
    logger.info(f"  醸造所 (JP): {enriched_info.get('brewery_name_jp')}")
    logger.info(f"  ビール (EN): {enriched_info.get('beer_name_en')}")
    logger.info(f"  ビール (JP): {enriched_info.get('beer_name_jp')}")
    logger.info(f"  種類: {enriched_info.get('product_type', 'beer')}")
    
    # Geminiデータを保存
    logger.info("\n💾 Geminiデータを保存中...")
    from datetime import datetime, timezone
    payload = {
        'url': url,
        'brewery_name_en': enriched_info.get('brewery_name_en'),
        'brewery_name_jp': enriched_info.get('brewery_name_jp'),
        'beer_name_en': enriched_info.get('beer_name_en'),
        'beer_name_jp': enriched_info.get('beer_name_jp'),
        'product_type': enriched_info.get('product_type', 'beer'),
        'is_set': enriched_info.get('is_set', False),
        'payload': enriched_info.get('raw_response'),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    supabase.table('gemini_data').upsert(payload).execute()
    logger.info("✓ 保存完了")
    
    # Untappdエンリッチメント（ビールの場合のみ）
    if enriched_info.get('product_type', 'beer') == 'beer':
        logger.info("\n🍺 Untappd URLを検索中...")
        
        brewery_name = enriched_info.get('brewery_name_en')
        beer_name = enriched_info.get('beer_name_en')
        
        if not brewery_name or not beer_name:
            logger.warning("⚠️  醸造所名またはビール名が不足しています。Untappd検索をスキップします。")
        else:
            untappd_result = get_untappd_url(brewery_name, beer_name)
            
            if untappd_result['success']:
                untappd_url = untappd_result['url']
                logger.info(f"✓ Untappd URL: {untappd_url}")
                
                # Untappd URLを保存
                logger.info("💾 Untappd URLを保存中...")
                supabase.table('scraped_beers').update({
                    'untappd_url': untappd_url
                }).eq('url', url).execute()
                logger.info("✓ 保存完了")
            else:
                logger.warning(f"⚠️  Untappd URLが見つかりませんでした: {untappd_result.get('reason', 'Unknown')}")
                
                # 失敗を記録
                failure_payload = {
                    'url': url,
                    'brewery_name': brewery_name,
                    'beer_name': beer_name,
                    'failure_reason': untappd_result.get('reason', 'Unknown'),
                    'attempted_at': datetime.now(timezone.utc).isoformat()
                }
                supabase.table('untappd_search_failures').upsert(failure_payload, on_conflict='url').execute()
    else:
        logger.info(f"\n⏭️  種類が '{enriched_info.get('product_type')}' のため、Untappd検索をスキップします")
    
    logger.info("\n" + "=" * 70)
    logger.info("✨ エンリッチメント完了！")
    logger.info("=" * 70)

async def main():
    url = "https://www.arome.jp/products/detail.php?product_id=5725"
    await enrich_specific_url(url)

if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
Arome専用再スクレイプスクリプト
- Aromeの全件を再スクレイプ
- 他ショップの最古first_seenより古いタイムスタンプを設定
- Arome内での新着順は保持
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.src.scrapers import arome

# Get Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Supabase credentials must be set")
    sys.exit(1)


async def rescrape_arome():
    print("=" * 60)
    print("🍺 Arome 再スクレイプ (first_seen を他ショップより古く設定)")
    print("=" * 60)
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. 他ショップの最古 first_seen を取得
    print("\n📅 他ショップの最古タイムスタンプを取得中...")
    response = supabase.table('scraped_beers') \
        .select('first_seen') \
        .neq('shop', 'Arome') \
        .order('first_seen', desc=False) \
        .limit(1) \
        .execute()
    
    if response.data:
        oldest_other = datetime.fromisoformat(response.data[0]['first_seen'].replace('Z', '+00:00'))
        print(f"  他ショップの最古: {oldest_other}")
    else:
        oldest_other = datetime.now(timezone.utc)
        print("  他ショップのデータがありません。現在時刻を基準にします。")
    
    # 基準時刻: 他ショップの最古より1日前
    base_time = oldest_other - timedelta(days=1)
    print(f"  Aromeの基準時刻: {base_time}")
    
    # 2. 既存のAromeデータを取得（untappd_urlを保持するため）
    print("\n📂 既存のAromeデータを取得中...")
    existing_arome = []
    chunk_size = 1000
    start = 0
    
    while True:
        res = supabase.table('scraped_beers') \
            .select('url, untappd_url') \
            .eq('shop', 'Arome') \
            .range(start, start + chunk_size - 1) \
            .execute()
        
        if not res.data:
            break
        existing_arome.extend(res.data)
        if len(res.data) < chunk_size:
            break
        start += chunk_size
    
    existing_data = {item['url']: item for item in existing_arome}
    print(f"  既存Arome: {len(existing_data)} 件")
    
    # 3. Aromeをフルスクレイプ
    print("\n🔍 Arome をフルスクレイプ中...")
    scraped_items = await arome.scrape_arome(limit=None, existing_urls=None, full_scrape=True)
    print(f"  スクレイプ件数: {len(scraped_items)} 件")
    
    if not scraped_items:
        print("❌ スクレイプ結果が空です")
        return
    
    # 4. タイムスタンプを割り当て（古い順に処理）
    # scraped_items は 新着→古い の順なので reverse
    items_to_process = list(reversed(scraped_items))
    
    current_time = datetime.now(timezone.utc)
    current_time_iso = current_time.isoformat()
    
    beers_to_upsert = []
    
    for i, item in enumerate(items_to_process):
        url = item.get('url')
        if not url:
            continue
        
        # マイクロ秒単位で増加（順序保持）
        item_time = base_time + timedelta(microseconds=i)
        item_time_iso = item_time.isoformat()
        
        beer_data = {
            'url': url,
            'name': item.get('name'),
            'price': item.get('price'),
            'image': item.get('image'),
            'stock_status': item.get('stock_status'),
            'shop': item.get('shop'),
            'first_seen': item_time_iso,
            'last_seen': current_time_iso,
        }
        
        # 既存のuntappd_urlを保持
        existing = existing_data.get(url)
        if existing and existing.get('untappd_url'):
            beer_data['untappd_url'] = existing.get('untappd_url')
        
        beers_to_upsert.append(beer_data)
    
    # 5. バッチアップサート
    if beers_to_upsert:
        batch_size = 500
        for i in range(0, len(beers_to_upsert), batch_size):
            batch = beers_to_upsert[i:i + batch_size]
            print(f"\n💾 Upserting batch {i // batch_size + 1} ({len(batch)} beers)...")
            try:
                supabase.table('scraped_beers').upsert(batch, on_conflict='url').execute()
                print(f"  ✅ Upserted {len(batch)} beers")
            except Exception as e:
                print(f"  ❌ Error: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ 完了: {len(beers_to_upsert)} 件のAromeビールを更新")
    print(f"   first_seen 範囲: {base_time} 〜 {base_time + timedelta(microseconds=len(beers_to_upsert))}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(rescrape_arome())

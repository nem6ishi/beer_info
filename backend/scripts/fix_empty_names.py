import asyncio
import os
import sys
import httpx
from bs4 import BeautifulSoup
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.core.db import get_supabase_client, sync_execute

async def fix_empty_names():
    sb = get_supabase_client()
    print("🔍 データベースから名前が空のビールを検索中...")
    res = sync_execute(sb.table('scraped_beers').select('url, shop').eq('name', ''))
    items = res.data or []
    
    if not items:
        print("✅ 名前が空のビールは見つかりませんでした。")
        return
        
    print(f"⚠️ {len(items)}件の空のビールが見つかりました。詳細ページから名前を取得して更新します。")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for item in items:
            url = item['url']
            shop = item['shop']
            print(f"  -> Fetching: {url} ({shop})")
            
            try:
                # EUC-JPの場合も考慮して自動判定させるか、utf-8で一旦受けてsoupで直す
                response = await client.get(url)
                
                # beervolta は euc-jp
                if 'beervolta' in url.lower():
                    response.encoding = 'euc-jp'
                elif 'ichigo_ichie' in url.lower():
                    response.encoding = 'euc-jp'
                else:
                    response.encoding = response.encoding or 'utf-8'
                
                soup = BeautifulSoup(response.text, "html.parser")
                title_tag = soup.find('title')
                
                if title_tag:
                    raw_title = title_tag.get_text(strip=True)
                    # " - BEER VOLTA" などを除去
                    name = raw_title.split('-')[0].strip()
                    # SALE表記なども除去
                    name = re.sub(r'SALE!!?\s*', '', name)
                    
                    if name:
                        print(f"     ✅ Found name: {name}")
                        sync_execute(sb.table('scraped_beers').update({'name': name}).eq('url', url))
                    else:
                        print(f"     ❌ Name is still empty after cleanup: {raw_title}")
                else:
                    print(f"     ❌ Title tag not found.")
                    
            except Exception as e:
                print(f"     ❌ Error fetching {url}: {e}")
                
    # 最後にマテリアライズドビューを更新
    print("\n🔄 ビュー (beer_info_view) をリフレッシュしています...")
    sync_execute(sb.rpc('refresh_beer_info_view'))
    print("✨ 完了しました！")

if __name__ == "__main__":
    asyncio.run(fix_empty_names())

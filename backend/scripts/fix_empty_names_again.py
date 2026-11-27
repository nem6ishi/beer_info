import asyncio
import os
import sys
import httpx
from bs4 import BeautifulSoup
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.core.db import get_supabase_client, sync_execute

urls_to_fix = [
    'https://beervolta.com/?pid=186746879',
    'https://beervolta.com/?pid=186926169',
    'https://beervolta.com/?pid=192697139',
    'https://beervolta.com/?pid=192718242',
    'https://beervolta.com/?pid=192718243',
    'https://beervolta.com/?pid=192735538'
]

async def fix_names_again():
    sb = get_supabase_client()
    print("⚠️ 再取得を開始します...")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for url in urls_to_fix:
            print(f"  -> Fetching: {url}")
            
            try:
                response = await client.get(url)
                response.encoding = 'euc-jp'
                
                soup = BeautifulSoup(response.text, "html.parser")
                title_tag = soup.find('title')
                
                if title_tag:
                    raw_title = title_tag.get_text(strip=True)
                    # " - BEER VOLTA" などを正確に除去
                    name = raw_title.replace(' - BEER VOLTA', '').strip()
                    # SALE表記なども除去
                    name = re.sub(r'SALE!!?\s*', '', name)
                    
                    if name:
                        print(f"     ✅ Fixed name: {name}")
                        sync_execute(sb.table('scraped_beers').update({'name': name}).eq('url', url))
                else:
                    print(f"     ❌ Title tag not found.")
                    
            except Exception as e:
                print(f"     ❌ Error fetching {url}: {e}")
                
    print("\n🔄 ビュー (beer_info_view) をリフレッシュしています...")
    sync_execute(sb.rpc('refresh_beer_info_view'))
    print("✨ 完了しました！")

if __name__ == "__main__":
    asyncio.run(fix_names_again())

import asyncio
import os
import sys
import httpx
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.core.db import get_supabase_client, sync_execute

async def check_beervolta():
    print("--- BEER VOLTA ---")
    sb = get_supabase_client()
    url = "https://beervolta.com/?mode=cate&cbid=2270431&csid=0&sort=n"
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # まず1ページ目にアクセスして最後のページ番号を探す
        res = await client.get(url)
        res.encoding = 'euc-jp'
        soup = BeautifulSoup(res.text, "html.parser")
        
        # ページネーションを探す
        page_links = soup.find_all('a', href=lambda h: h and 'page=' in h)
        pages = [int(a['href'].split('page=')[1].split('&')[0]) for a in page_links if 'page=' in a['href']]
        last_page = max(pages) if pages else 1
        
        print(f"BeerVolta 最後のページ: {last_page}")
        
        # 最後のページにアクセス
        last_url = f"{url}&page={last_page}"
        res2 = await client.get(last_url)
        res2.encoding = 'euc-jp'
        soup2 = BeautifulSoup(res2.text, "html.parser")
        
        items = soup2.find_all('a', href=lambda h: h and '?pid=' in h)
        if items:
            test_item = items[0]
            href = test_item.get('href')
            item_url = f"https://beervolta.com{href}" if href.startswith('/') else (href if href.startswith('http') else f"https://beervolta.com/{href}")
            print(f"最後のページの商品例: {item_url}")
            
            # DB確認
            db_res = sync_execute(sb.table('scraped_beers').select('url').eq('url', item_url))
            if db_res.data:
                print("✅ DBに存在します（全件完了の根拠あり）")
            else:
                print("❌ DBに存在しません！（途中で止まっている可能性あり）")

if __name__ == "__main__":
    asyncio.run(check_beervolta())

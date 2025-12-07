import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '10'))

async def scrape_ichigo_ichie(limit: int = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Ichigo Ichie (https://151l.shop/).
    Now supports pagination to get all beers.
    Stops early if too many consecutive sold-out items are found.
    """
    base_url = "https://151l.shop/?mode=grp&gid=1978037&sort=n&page={}"  # 全てのビール一覧
    products = []
    consecutive_sold_out = 0
    
    async with httpx.AsyncClient() as client:
        for page_num in range(1, 800):  # Safety limit 800 pages (actual is 770)
            # Check global limit
            if limit and len(products) >= limit:
                break

            url = base_url.format(page_num)
            print(f"[Ichigo Ichie] Scraping page {page_num}: {url}")
            
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                
                if response.status_code != 200:
                    print(f"[Ichigo Ichie] Failed to load page {page_num}: {response.status_code}")
                    break

                # Robust decoding for Japanese sites
                content = None
                encodings = ['euc-jp', 'shift_jis', 'utf-8']
                for enc in encodings:
                    try:
                        content = response.content.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if not content:
                    content = response.content.decode('utf-8', errors='replace')

                soup = BeautifulSoup(content, 'lxml')
                
                # Select product items
                items = soup.select('li.productlist_list')
                
                if not items:
                    print(f"[Ichigo Ichie] No items found on page {page_num}. Stopping.")
                    break
                
                page_item_count = 0
                for item in items:
                    try:
                        # Detail URL & Image
                        link_tag = item.find('a')
                        if not link_tag:
                            continue
                            
                        href = link_tag.get('href', '')
                        product_url = f"https://151l.shop/{href}" if not href.startswith('http') else href
                        
                        img_tag = item.select_one('img.item_img')
                        image_url = None
                        if img_tag:
                            src = img_tag.get('src', '')
                            image_url = src if src.startswith('http') else f"https://151l.shop{src}"

                        # Name
                        name = "Unknown"
                        name_tag = item.select_one('span.item_name')
                        if name_tag:
                            name = name_tag.get_text(strip=True)

                        # Price
                        price = "Unknown"
                        price_tag = item.select_one('span.item_price')
                        if price_tag:
                            price = price_tag.get_text(strip=True)
                        
                        # Stock Status
                        stock_status = "In Stock"
                        if "SOLD OUT" in item.get_text().upper():
                             stock_status = "Sold Out"
                             consecutive_sold_out += 1
                        else:
                            consecutive_sold_out = 0
                        
                        products.append({
                            "name": name,
                            "price": price,
                            "url": product_url,
                            "image": image_url,
                            "stock_status": stock_status,
                            "shop": "一期一会～る"
                        })
                        
                        page_item_count += 1
                        
                        # Check if we've hit the consecutive sold-out threshold
                        if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                            print(f"[Ichigo Ichie] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                            break
                        
                        # Check Limit
                        if limit and len(products) >= limit:
                            break
                            
                    except Exception as e:
                        print(f"[Ichigo Ichie] Error parsing item: {e}")
                        continue
                
                print(f"[Ichigo Ichie] Found {page_item_count} items on page {page_num}")
                
                # Check if early stop was triggered
                if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Ichigo Ichie] Stopping pagination due to consecutive sold-out items.")
                    break
                
                # If no items found on this page, stop
                if page_item_count == 0:
                    print(f"[Ichigo Ichie] No valid items found on page {page_num}. Stopping.")
                    break
                
            except Exception as e:
                print(f"[Ichigo Ichie] Error fetching page {page_num}: {e}")
                break
            
    print(f"[Ichigo Ichie] Extracted {len(products)} products.")
    return products

if __name__ == "__main__":
    import json
    data = asyncio.run(scrape_ichigo_ichie())
    print(json.dumps(data, indent=2, ensure_ascii=False))

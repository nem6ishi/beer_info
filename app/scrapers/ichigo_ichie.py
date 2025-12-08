import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

async def scrape_ichigo_ichie(limit: int = None, existing_urls: set = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Ichigo Ichie (https://151l.shop/).
    Now supports pagination to get all beers.
    Stops early if too many consecutive sold-out items are found.
    """
    base_url = "https://151l.shop/?mode=grp&gid=1978037&sort=n&page={}"  # 全てのビール一覧
    products = []
    consecutive_sold_out = 0
    
    async with httpx.AsyncClient() as client:
        start_page = 1
        end_page = 800
        step = 1

        if existing_urls is not None:
             print(f"[Ichigo Ichie] Smart Mode: Forward Scrape & Buffer...")
             
             scan_page = 1
             consecutive_existing = 0
             stop_scan = False
             
             while not stop_scan:
                 url = base_url.format(scan_page)
                 print(f"[Ichigo Ichie] Smart Scrape {scan_page}: {url}")
                 try:
                     response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                     if response.status_code != 200:
                         break
                         
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
                     items = soup.select('li.productlist_list')
                     
                     if not items:
                         break
                         
                     page_items = []
                     
                     for item in items:
                        try:
                             # Parsing logic
                             link_tag = item.find('a')
                             if not link_tag: continue
                             href = link_tag.get('href', '')
                             product_url = f"https://151l.shop/{href}" if not href.startswith('http') else href
                             
                             if product_url in existing_urls:
                                 consecutive_existing += 1
                             else:
                                 consecutive_existing = 0

                             img_tag = item.select_one('img.item_img')
                             image_url = None
                             if img_tag:
                                 src = img_tag.get('src', '')
                                 image_url = src if src.startswith('http') else f"https://151l.shop{src}"

                             name = "Unknown"
                             name_tag = item.select_one('span.item_name')
                             if name_tag: name = name_tag.get_text(strip=True)

                             price = "Unknown"
                             price_tag = item.select_one('span.item_price')
                             if price_tag:
                                 raw_price = price_tag.get_text(strip=True)
                                 match = re.search(r'税込([0-9,]+円)', raw_price)
                                 if match: price = match.group(1)
                                 else: price = raw_price
                             
                             stock_status = "In Stock"
                             if "SOLD OUT" in item.get_text().upper():
                                  stock_status = "Sold Out"
                             
                             p_item = {
                                 "name": name,
                                 "price": price,
                                 "url": product_url,
                                 "image": image_url,
                                 "stock_status": stock_status,
                                 "shop": "一期一会～る"
                             }
                             
                             products.append(p_item)
                             page_items.append(p_item)
                             
                             if limit and len(products) >= limit:
                                 print(f"[Ichigo Ichie] Limit reached ({limit}). Stopping scan.")
                                 stop_scan = True
                                 break
                                 
                             # Existing item check removed
                             # if consecutive_existing >= 10:
                             #     print(f"[Ichigo Ichie] Found 10 consecutive existing items. Stopping scan.")
                             #     stop_scan = True
                             #     break

                        except Exception as e:
                             print(f"[Ichigo Ichie] Error parsing item: {e}")
                             continue
                     
                     if not stop_scan:
                         scan_page += 1
                         # if scan_page > 800: break
                         
                 except Exception as e:
                     print(f"[Ichigo Ichie] Error scanning page {scan_page}: {e}")
                     break
             
             print(f"[Ichigo Ichie] Smart Scrape Finished. Buffered {len(products)} items.")
             return products

        
        # Infinite loop until error or empty
        page_num = start_page
        while True:
            # Check global limit
            if limit and len(products) >= limit:
                break

            url = base_url.format(page_num)
            print(f"[Ichigo Ichie] Scraping page {page_num}: {url}")
            
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                if response.status_code != 200:
                    print(f"[Ichigo Ichie] Failed to load page {page_num}. Stopping.")
                    break

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
                items = soup.select('li.productlist_list')
                
                if not items:
                    print(f"[Ichigo Ichie] No items found on page {page_num}. Stopping.")
                    break
                
                page_products = []
                for item in items:
                    try:
                        # Parsing logic
                        link_tag = item.find('a')
                        if not link_tag: continue
                        href = link_tag.get('href', '')
                        product_url = f"https://151l.shop/{href}" if not href.startswith('http') else href
                        
                        img_tag = item.select_one('img.item_img')
                        image_url = None
                        if img_tag:
                            src = img_tag.get('src', '')
                            image_url = src if src.startswith('http') else f"https://151l.shop{src}"

                        name = "Unknown"
                        name_tag = item.select_one('span.item_name')
                        if name_tag: name = name_tag.get_text(strip=True)

                        price = "Unknown"
                        price_tag = item.select_one('span.item_price')
                        if price_tag:
                            raw_price = price_tag.get_text(strip=True)
                            # Try to extract tax included price: 1,050円(税込1,155円) -> 1,155円
                            # Also handle potential variations like "税込1,155円" or just "1,155円"
                            match = re.search(r'税込([0-9,]+円)', raw_price)
                            if match:
                                price = match.group(1)
                            else:
                                # Fallback to raw if no specific tax formatting found,
                                # but try to clean it up if it's just the number part
                                price = raw_price
                        
                        stock_status = "In Stock"
                        if "SOLD OUT" in item.get_text().upper():
                             stock_status = "Sold Out"
                        
                        page_products.append({
                            "name": name,
                            "price": price,
                            "url": product_url,
                            "image": image_url,
                            "stock_status": stock_status,
                            "shop": "一期一会～る"
                        })
                    except Exception as e:
                        print(f"[Ichigo Ichie] Error parsing item: {e}")
                        continue
                
                for p in page_products:
                    if p['stock_status'] == "Sold Out":
                        consecutive_sold_out += 1
                    else:
                        consecutive_sold_out = 0
                    
                    if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                         print(f"[Ichigo Ichie] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                         pass

                    products.append(p)
                    if limit and len(products) >= limit: break
                
                if limit and len(products) >= limit: break
                
                if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Ichigo Ichie] Stopping pagination due to consecutive sold-out items.")
                    break
                
                print(f"[Ichigo Ichie] Found {len(page_products)} items on page {page_num}")
                
                if not page_products:
                     break

                page_num += 1
                
            except Exception as e:
                print(f"[Ichigo Ichie] Error fetching page {page_num}: {e}")
                break
            
    print(f"[Ichigo Ichie] Extracted {len(products)} products.")
    return products

if __name__ == "__main__":
    import json
    data = asyncio.run(scrape_ichigo_ichie(limit=5))
    print(json.dumps(data, indent=2, ensure_ascii=False))

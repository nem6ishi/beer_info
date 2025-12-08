import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

async def scrape_ichigo_ichie(limit: int = None, reverse: bool = False, start_page_hint: int = None, existing_urls: set = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Ichigo Ichie (https://151l.shop/).
    Now supports pagination to get all beers.
    Stops early if too many consecutive sold-out items are found (DISABLED if reverse=True).
    """
    base_url = "https://151l.shop/?mode=grp&gid=1978037&sort=n&page={}"  # 全てのビール一覧
    products = []
    consecutive_sold_out = 0
    
    async with httpx.AsyncClient() as client:
        start_page = 1
        end_page = 800
        step = 1
        max_page_found = None
        
        # If reverse, calculate max page from total items
        if reverse:
            print("[Ichigo Ichie] Reverse mode: Calculating max page...")
            
            # Optimization: Check if hint+1 exists first
            skip_scan = False
            if start_page_hint and start_page_hint > 0:
                print(f"[Ichigo Ichie] checking hint+1 ({start_page_hint + 1})")
                try:
                    # Quick Probe
                    r = await client.get(base_url.format(start_page_hint + 1), headers={"User-Agent": "Mozilla/5.0"}, timeout=15.0)
                    # Check status and basic content "NO ITEMS" check without parsing full soup if possible
                    # Ichigo Ichie returns 200 even for empty pages usually, but let's check content length or "0商品"
                    has_new_items = False
                    if r.status_code == 200:
                         # Simple text check first
                         txt = r.text
                         # "該当する商品がありません" or 0 items
                         if "該当する商品がありません" not in txt and "全<span>0</span>商品" not in txt:
                              # It MIGHT have items.
                              # Let's verify with soup just to be safe, or assume yes?
                              # Safety: parse soup
                              soup_probe = BeautifulSoup(txt, 'lxml')
                              if soup_probe.select('li.productlist_list'):
                                   has_new_items = True

                    if not has_new_items:
                        print(f"[Ichigo Ichie] No items on page {start_page_hint + 1}. Keeping max page as {start_page_hint}.")
                        max_page_found = start_page_hint
                        skip_scan = True
                    else:
                        print(f"[Ichigo Ichie] Found items on {start_page_hint + 1}. Rescanning total count.")
                except Exception as e:
                    print(f"[Ichigo Ichie] Probe failed: {e}. Proceeding with full scan.")

            if not skip_scan:
                print("[Ichigo Ichie] Fetching Page 1 for total count...")
                try:
                    # Fetch page 1
                    response = await client.get(base_url.format(1), headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                    
                    # Decode
                    content = None
                    encodings = ['euc-jp', 'shift_jis', 'utf-8']
                    for enc in encodings:
                        try:
                            content = response.content.decode(enc)
                            break
                        except: continue
                    if not content: content = response.content.decode('utf-8', errors='replace')
                    
                    # Parse total items from <div class="pagerlist_pos">全<span>9243</span>商品...
                    # or similar pattern
                    match = re.search(r'全<span>(\d+)</span>商品', content)
                    if match:
                        total_items = int(match.group(1))
                        items_per_page = 12 # Default for this site
                        # Try to find items per page if dynamic
                        # ... 1-12表示 ...
                        range_match = re.search(r'(\d+)-(\d+)表示', content)
                        if range_match:
                            per_page_diff = int(range_match.group(2)) - int(range_match.group(1)) + 1
                            if per_page_diff > 0:
                                items_per_page = per_page_diff
                        
                        max_page_found = (total_items + items_per_page - 1) // items_per_page
                        print(f"[Ichigo Ichie] Total items: {total_items}, Per page: {items_per_page} -> Last page: {max_page_found}")
                    else:
                        print("[Ichigo Ichie] Could not parse total items. Fallback to Page 800 scan.")
                        max_page_found = 800 # Fallback start
                except Exception as e:
                    print(f"[Ichigo Ichie] Error finding last page: {e}. Defaulting to Page 800.")
                    max_page_found = 800

            start_page = max_page_found
            
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
                     
                     content = None
                     encodings = ['euc-jp', 'shift_jis', 'cp932', 'utf-8']
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
                         
                     # Scrape items
                     page_products = []
                     
                     for item in items:
                         try:
                            link_tag = item.find('a')
                            if not link_tag: continue
                            href = link_tag.get('href', '')
                            product_url = f"https://151l.shop/{href}" if not href.startswith('http') else href
                            
                            # Check existing
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
                                if match:
                                    price = match.group(1)
                                else:
                                    price = raw_price
                            
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
                            page_products.append(p_item)
                         
                            if limit and len(products) >= limit:
                                print(f"[Ichigo Ichie] Limit reached ({limit}). Stopping scan.")
                                stop_scan = True
                                break

                            if consecutive_existing >= 10:
                                print(f"[Ichigo Ichie] Found 10 consecutive existing items. Stopping scan.")
                                stop_scan = True
                                break
                         except Exception as e:
                             print(f"[Ichigo Ichie] Error parsing item: {e}")
                             continue

                     if not stop_scan:
                         scan_page += 1
                         if scan_page > 80: # deeper
                             print("[Ichigo Ichie] Scan limit reached (80). Stopping.")
                             break
                             
                 except Exception as e:
                     print(f"[Ichigo Ichie] Probe error {scan_page}: {e}")
                     break
             
             print(f"[Ichigo Ichie] Smart Scrape Finished. Buffered {len(products)} items.")
             return products, None # Return immediately

        for page_num in range(start_page, end_page, step):
            # Check global limit
            if limit and len(products) >= limit:
                break

            url = base_url.format(page_num)
            print(f"[Ichigo Ichie] Scraping page {page_num}: {url}")
            
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                if response.status_code != 200:
                    if reverse:
                        continue # Skip bad page in reverse
                    else:
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
                    if not reverse:
                        print(f"[Ichigo Ichie] No items found on page {page_num}. Stopping.")
                        break
                    else:
                        print(f"[Ichigo Ichie] No items on page {page_num}.")
                
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
                
                # If reverse and first time finding items, record this as max_page_found (if not already set)
                if reverse and page_products and max_page_found is None:
                    max_page_found = page_num
                    print(f"[Ichigo Ichie] Found max page during scan: {max_page_found}")
                        
                # Reverse items if needed
                if reverse:
                    page_products.reverse()
                
                for p in page_products:
                    # Sold out logic ONLY if not reverse
                    if not reverse:
                        if p['stock_status'] == "Sold Out":
                            consecutive_sold_out += 1
                        else:
                            consecutive_sold_out = 0
                        
                        if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                             print(f"[Ichigo Ichie] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                             # Add and stop? Or just mark stopping condition? 
                             # We'll just break loop
                             pass

                    products.append(p)
                    if limit and len(products) >= limit: break
                
                if limit and len(products) >= limit: break
                if not reverse and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Ichigo Ichie] Stopping pagination due to consecutive sold-out items.")
                    break
                
                if not reverse and not page_products:
                     break
                
                print(f"[Ichigo Ichie] Found {len(page_products)} items on page {page_num}")

            except Exception as e:
                print(f"[Ichigo Ichie] Error fetching page {page_num}: {e}")
                if not reverse: break
            
    print(f"[Ichigo Ichie] Extracted {len(products)} products.")
    return products, max_page_found

if __name__ == "__main__":
    import json
    data = asyncio.run(scrape_ichigo_ichie())
    print(json.dumps(data, indent=2, ensure_ascii=False))

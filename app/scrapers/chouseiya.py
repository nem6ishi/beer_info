import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from datetime import datetime

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

def extract_product_data(item):
    """Helper to extract product data from a soup item."""
    try:
        img_wrap = item.select_one('div.imgWrap')
        if not img_wrap: return None
        
        link_tag = img_wrap.find('a')
        img_tag = img_wrap.find('img')
        
        if not link_tag: return None
        
        href = link_tag.get('href')
        product_url = f"https://beer-chouseiya.shop{href}" if href.startswith('/') else href
        
        image_url = None
        if img_tag:
            src = img_tag.get('src')
            image_url = f"https://beer-chouseiya.shop{src}" if src.startswith('/') else src
        
        detail = item.select_one('div.detail')
        name = "Unknown"
        price = "Unknown"
        stock_status = "In Stock"
        
        if detail:
            name_tag = detail.select_one('p.name')
            if name_tag:
                name = name_tag.get_text(strip=True)
            
            price_tag = detail.select_one('p.price')
            if price_tag:
                price_text = price_tag.get_text(strip=True)
                price = price_text
                
            quantity_tag = detail.select_one('p.quantity')
            qty_text = quantity_tag.get_text(strip=True) if quantity_tag else ""
            detail_text = detail.get_text(strip=True)
            
            if "売り切れ" in qty_text or "0個" in qty_text:
                stock_status = "Sold Out"
            elif "売り切れ" in detail_text or "SOLD OUT" in detail_text.upper():
                stock_status = "Sold Out"
        
        return {
            "name": name,
            "price": price,
            "url": product_url,
            "image": image_url,
            "stock_status": stock_status,
            "shop": "ちょうせいや"
        }

    except Exception as e:
        print(f"[Chouseiya] Error parsing item: {e}")
        return None

async def scrape_chouseiya(limit: int = None, existing_urls: set = None, full_scrape: bool = False) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Chouseiya using httpx and BeautifulSoup.
    Handles EUC-JP encoding manually.
    Stops early if too many consecutive sold-out items are found, unless full_scrape is True.
    """
    base_url = "https://beer-chouseiya.shop/shopbrand/all_items/page{}/order/"
    all_items = []
    consecutive_sold_out = 0
    
    async with httpx.AsyncClient() as client:
        start_page = 1
        end_page = 50  # Arbitrary high number, loop breaks when 404
        step = 1

        if existing_urls is not None:
             print(f"[Chouseiya] Smart Mode: Forward Scrape & Buffer...")
             
             scan_page = 1
             consecutive_existing = 0
             stop_scan = False
             
             while not stop_scan:
                 url = base_url.format(scan_page)
                 print(f"[Chouseiya] Smart Scrape {scan_page}: {url}")
                 
                 try:
                     response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                     if response.status_code == 404:
                         break
                         
                     # Decode
                     content = None
                     encodings_to_try = ['euc-jp', 'cp932', 'shift_jis', 'utf-8']
                     for encoding in encodings_to_try:
                        try:
                            content = response.content.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                     
                     if not content:
                        content = response.content.decode('euc-jp', errors='replace')

                     soup = BeautifulSoup(content, 'lxml')
                     item_elements = soup.select('div.innerBox')
                     
                     if not item_elements:
                         break
                         
                     # Scrape items on this page
                     page_items = []
                     
                     for item in item_elements:
                        p_item = extract_product_data(item)
                        if not p_item: continue
                        
                        product_url = p_item['url']
                        
                        # Check existing
                        if product_url in existing_urls:
                            consecutive_existing += 1
                        else:
                            consecutive_existing = 0
                        
                        all_items.append(p_item)
                        page_items.append(p_item)
                        
                        if limit and len(all_items) >= limit:
                            print(f"[Chouseiya] Limit reached ({limit}). Stopping scan.")
                            stop_scan = True
                            break
                        
                        # Existing item check removed
                        # if consecutive_existing >= 10:
                        #    print(f"[Chouseiya] Found 10 consecutive existing items. Stopping scan.")
                        #    stop_scan = True
                        #    break
                     
                     if not stop_scan:
                         scan_page += 1
                         # Scan limit removed
                         # if scan_page > 500:
                         #     print("[Chouseiya] Scan limit reached (500). Stopping.")
                         #     break
                             
                 except Exception as e:
                     print(f"[Chouseiya] Error scanning page {scan_page}: {e}")
                     break
            
             print(f"[Chouseiya] Smart Scrape Finished. Buffered {len(all_items)} items.")
             return all_items # Return immediately
        
        
        # Infinite loop until 404 or empty
        page_num = start_page
        while True:
            # Check global limit
            if limit and len(all_items) >= limit:
                break

            url = base_url.format(page_num)
            print(f"[Chouseiya] Scraping page {page_num}: {url}")
            
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                
                if response.status_code == 404:
                    print(f"[Chouseiya] Page {page_num} not found. Stopping.")
                    break
                
                # Robust decoding
                content = None
                encodings_to_try = ['euc-jp', 'cp932', 'shift_jis', 'utf-8']
                for encoding in encodings_to_try:
                    try:
                        content = response.content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if content:
                    soup = BeautifulSoup(content, 'lxml')
                else:
                    soup = BeautifulSoup(response.content, 'lxml')

                # Extract items
                item_elements = soup.select('div.innerBox')
                
                page_items = []
                
                if not item_elements:
                    print(f"[Chouseiya] No items (div.innerBox) found on page {page_num}. Stopping.")
                    break
                
                for item in item_elements:
                    p_item = extract_product_data(item)
                    if not p_item: continue
                    
                    page_items.append(p_item)
                
                for p_item in page_items:
                    if p_item['stock_status'] == "Sold Out":
                        consecutive_sold_out += 1
                    else:
                        consecutive_sold_out = 0
                        
                    # Check threshold
                    if not full_scrape and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                        print(f"[Chouseiya] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                        pass 

                    all_items.append(p_item)
                    if limit and len(all_items) >= limit:
                        break
                
                if limit and len(all_items) >= limit:
                    break

                if not full_scrape and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Chouseiya] Stopping pagination due to consecutive sold-out items.")
                    break
                
                print(f"[Chouseiya] Found {len(page_items)} items on page {page_num}")
                
                if not page_items:
                    print(f"[Chouseiya] No valid items found on page {page_num}. Stopping.")
                    break

                page_num += 1

            except Exception as e:
                print(f"[Chouseiya] Error fetching page {page_num}: {e}")
                break
                
    print(f"[Chouseiya] Extracted {len(all_items)} products.")
    return all_items

if __name__ == "__main__":
    items = asyncio.run(scrape_chouseiya(limit=5))
    print(items[:2])

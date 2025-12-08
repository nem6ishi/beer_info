import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from datetime import datetime

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

async def scrape_chouseiya(limit: int = None, reverse: bool = False, start_page_hint: int = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Chouseiya using httpx and BeautifulSoup.
    Handles EUC-JP encoding manually.
    Stops early if too many consecutive sold-out items are found (DISABLED if reverse=True).
    """
    base_url = "https://beer-chouseiya.shop/shopbrand/all_items/page{}/order/"
    all_items = []
    consecutive_sold_out = 0
    
    async with httpx.AsyncClient() as client:
        start_page = 1
        end_page = 50
        step = 1
        max_page_found = None
        
        # If reverse, use Binary Search to find the exact last page
        if reverse:
            print(f"[Chouseiya] Reverse mode: Detecting last page (Hint: {start_page_hint})...")
            
            async def has_items(p_num):
                try:
                    r = await client.get(base_url.format(p_num), headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0)
                    if r.status_code == 404: return False
                    # Decode
                    txt = r.content.decode('euc-jp', errors='replace') # Try primary encoding
                    if 'innerBox' or 'item_data' in txt: # Basic check without full parse
                         # Verify strictly with bs4 if needed, but text search is faster
                         return '<div class="innerBox">' in txt or 'class="name"' in txt
                    return False
                except:
                    return False

            # Optimization: If hint provided, check if next page exists
            low = 1
            high = 100
            
            if start_page_hint and start_page_hint > 0:
                print(f"[Chouseiya] Checking if pages exist after {start_page_hint}...")
                if await has_items(start_page_hint + 1):
                    print(f"[Chouseiya] Found items on page {start_page_hint + 1}. Searching for new max...")
                    low = start_page_hint + 1
                    high = start_page_hint + 20 # Expand range? or just 100
                    if high < 100: high = 100
                else:
                    print(f"[Chouseiya] No items on page {start_page_hint + 1}. Max page is likely {start_page_hint}.")
                    low = start_page_hint
                    high = start_page_hint # Skip search
            
            last_valid = low
            
            while low <= high:
                mid = (low + high) // 2
                if await has_items(mid):
                    last_valid = mid
                    low = mid + 1
                else:
                    high = mid - 1
            
            print(f"[Chouseiya] Detected last page: {last_valid}")
            max_page_found = last_valid
            start_page = last_valid
            
            # If we had a hint, we stop scraping when we reach the hint page (inclusive) or pass it?
            # User wants to check "after" it. Scrape new pages.
            # Usually we scrape from Max -> Down.
            # If Max=55, Hint=50. Scrape 55, 54, 53, 52, 51. (And 50?)
            # Let's scrape 50 too just in case it got filled.
            if start_page_hint and start_page_hint > 0:
                end_page = start_page_hint - 1 
            else:
                end_page = 0
            
            step = -1
        else:
             # Normal mode: We don't know the max page unless we scan.
             # But for metadata purposes, we might want to scan?
             # User said: "When scraping, first check if last page changed."
             # Assuming this check primarily happens in Reverse/Full scrape context.
             # For now, return None if not detected.
             pass

        # Loop through pages
        for page_num in range(start_page, end_page, step):
            # Check global limit
            if limit and len(all_items) >= limit:
                break

            url = base_url.format(page_num)
            print(f"[Chouseiya] Scraping page {page_num}: {url}")
            
            try:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                
                if response.status_code == 404:
                    if reverse:
                        print(f"[Chouseiya] Page {page_num} not found (unexpected in reverse). Continuing.")
                        continue
                    else:
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
                    # Only stop if in normal mode, otherwise might be a gap
                    if not reverse:
                        print(f"[Chouseiya] No items (div.innerBox) found on page {page_num}. Stopping.")
                        break
                    else:
                        print(f"[Chouseiya] No items found on page {page_num}.")
                
                for item in item_elements:
                    try:
                        # Extract Image and potentially URL (from imgWrap)
                        img_wrap = item.select_one('div.imgWrap')
                        if not img_wrap: continue
                        
                        link_tag = img_wrap.find('a')
                        img_tag = img_wrap.find('img')
                        
                        if not link_tag: continue
                        
                        href = link_tag.get('href')
                        product_url = f"https://beer-chouseiya.shop{href}" if href.startswith('/') else href
                        
                        image_url = None
                        if img_tag:
                            src = img_tag.get('src')
                            image_url = f"https://beer-chouseiya.shop{src}" if src.startswith('/') else src
                        
                        # Extract Details
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
                                
                            # Robust Stock Status Detection
                            quantity_tag = detail.select_one('p.quantity')
                            qty_text = quantity_tag.get_text(strip=True) if quantity_tag else ""
                            detail_text = detail.get_text(strip=True)
                            
                            if "売り切れ" in qty_text or "0個" in qty_text:
                                stock_status = "Sold Out"
                            elif "売り切れ" in detail_text or "SOLD OUT" in detail_text.upper():
                                stock_status = "Sold Out"
                        
                        page_items.append({
                            "name": name,
                            "price": price,
                            "url": product_url,
                            "image": image_url,
                            "stock_status": stock_status,
                            "shop": "ちょうせいや"
                        })

                    except Exception as e:
                        print(f"[Chouseiya] Error parsing item: {e}")
                        continue
                
                # In REVERSE mode, we iterate items from bottom to top (Last Item -> First Item)
                if reverse:
                    page_items.reverse()
                
                # Check consecutive sold out ONLY IF NOT REVERSE (or user wants it disabled in reverse)
                # Usually we disable it in reverse because old items are often sold out.
                
                for p_item in page_items:
                    if not reverse:
                        if p_item['stock_status'] == "Sold Out":
                            consecutive_sold_out += 1
                        else:
                            consecutive_sold_out = 0
                            
                        # Check threshold
                        if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                            print(f"[Chouseiya] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                            all_items.extend(page_items[:page_items.index(p_item)+1]) # Add up to this one? Or stop before?
                            # Actually, we should break outer loop. 
                            # Let's just add it and break.
                            pass 

                    all_items.append(p_item)
                    if limit and len(all_items) >= limit:
                        break
                
                if limit and len(all_items) >= limit:
                    break

                if not reverse and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Chouseiya] Stopping pagination due to consecutive sold-out items.")
                    break
                
                print(f"[Chouseiya] Found {len(page_items)} items on page {page_num}")
                
                # Optimistic stop if page was empty in normal mode
                if not reverse and not page_items:
                    print(f"[Chouseiya] No valid items found on page {page_num}. Stopping.")
                    break

            except Exception as e:
                print(f"[Chouseiya] Error fetching page {page_num}: {e}")
                if not reverse: break # In reverse, one failed page shouldn't kill the whole old batch maybe?
                
    print(f"[Chouseiya] Extracted {len(all_items)} products.")
    return all_items, max_page_found

if __name__ == "__main__":
    items = asyncio.run(scrape_chouseiya())
    print(items[:2])

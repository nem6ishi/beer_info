import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from datetime import datetime

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '10'))

async def scrape_chouseiya(limit: int = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Chouseiya using httpx and BeautifulSoup.
    Handles EUC-JP encoding manually.
    Stops early if too many consecutive sold-out items are found.
    """
    base_url = "https://beer-chouseiya.shop/shopbrand/all_items/page{}/order/"
    all_items = []
    consecutive_sold_out = 0
    
    async with httpx.AsyncClient() as client:
        for page_num in range(1, 50): # Increased to 50 pages to get all 1407 items
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
                
                # Robust decoding for Japanese legacy sites
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
                    print(f"[Chouseiya] Encoding detection failed for page {page_num}. Letting BeautifulSoup guess.")
                    soup = BeautifulSoup(response.content, 'lxml')

                items = soup.select('div.innerBox')
                if not items:
                    print(f"[Chouseiya] No items (div.innerBox) found on page {page_num}. Stopping.")
                    break
                
                page_item_count = 0
                for item in items:
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
                                
                            quantity_tag = detail.select_one('p.quantity')
                            if quantity_tag:
                                qty_text = quantity_tag.get_text(strip=True)
                                if "売り切れ" in qty_text or "0個" in qty_text:
                                    stock_status = "Sold Out"
                                    consecutive_sold_out += 1
                                else:
                                    consecutive_sold_out = 0
                            else:
                                consecutive_sold_out = 0
                        
                        all_items.append({
                            "name": name,
                            "price": price,
                            "url": product_url,
                            "image": image_url,
                            "shop": "ちょうせいや"
                        })
                        
                        page_item_count += 1
                        
                        # Check if we've hit the consecutive sold-out threshold
                        if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                            print(f"[Chouseiya] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                            break
                        
                        # Check Limit
                        if limit and len(all_items) >= limit:
                            break

                    except Exception as e:
                        print(f"[Chouseiya] Error parsing item: {e}")
                        continue
                
                print(f"[Chouseiya] Found {page_item_count} items on page {page_num}")
                
                # Check if early stop was triggered
                if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Chouseiya] Stopping pagination due to consecutive sold-out items.")
                    break
                
                # If no items found on this page, stop
                if page_item_count == 0:
                    print(f"[Chouseiya] No valid items found on page {page_num}. Stopping.")
                    break

            except Exception as e:
                print(f"[Chouseiya] Error fetching page {page_num}: {e}")
                break
                
    print(f"[Chouseiya] Extracted {len(all_items)} products.")
    return all_items

if __name__ == "__main__":
    items = asyncio.run(scrape_chouseiya())
    print(items[:2])

import asyncio
import os
import httpx
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Set, Any
import re
from datetime import datetime
from ..core.types import ScrapedProduct

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

def extract_product_data(item: Tag) -> Optional[ScrapedProduct]:
    """Helper to extract product data from a soup item."""
    try:
        img_wrap: Optional[Tag] = item.select_one('div.imgWrap')
        if not img_wrap: return None
        
        link_tag: Optional[Tag] = img_wrap.find('a')
        img_tag: Optional[Tag] = img_wrap.find('img')
        
        if not link_tag: return None
        
        href: Optional[str] = link_tag.get('href')
        if not href: return None
        
        product_url: str = f"https://beer-chouseiya.shop{href}" if href.startswith('/') else href
        
        # Normalize URL to remove pagination suffix
        if "/shopdetail/" in product_url:
            product_url = re.sub(r'(/shopdetail/[^/]+)(?:/.*)?$', r'\1', product_url)
        
        image_url: Optional[str] = None
        if img_tag:
            src: Optional[str] = img_tag.get('src')
            if src:
                image_url = f"https://beer-chouseiya.shop{src}" if src.startswith('/') else src
        
        detail: Optional[Tag] = item.select_one('div.detail')
        name: str = "Unknown"
        price: str = "Unknown"
        stock_status: str = "In Stock"
        
        if detail:
            name_tag: Optional[Tag] = detail.select_one('p.name')
            if name_tag:
                name = name_tag.get_text(strip=True)
            
            price_tag: Optional[Tag] = detail.select_one('p.price')
            if price_tag:
                price = price_tag.get_text(strip=True)
                
            quantity_tag: Optional[Tag] = detail.select_one('p.quantity')
            qty_text: str = quantity_tag.get_text(strip=True) if quantity_tag else ""
            detail_text: str = detail.get_text(strip=True)
            
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

async def scrape_chouseiya(limit: Optional[int] = None, existing_urls: Optional[Set[str]] = None, full_scrape: bool = False) -> List[ScrapedProduct]:
    """
    Scrapes product information from Chouseiya using httpx and BeautifulSoup.
    """
    base_url: str = "https://beer-chouseiya.shop/shopbrand/all_items/page{}/order/"
    all_items: List[ScrapedProduct] = []
    consecutive_sold_out: int = 0
    
    async with httpx.AsyncClient() as client:
        if existing_urls is not None:
             print(f"[Chouseiya] New Product Scrape: Forward Scrape & Buffer...")
             
             scan_page: int = 1
             consecutive_existing: int = 0
             stop_scan: bool = False
             
             while not stop_scan:
                 url: str = base_url.format(scan_page)
                 print(f"[Chouseiya] Smart Scrape {scan_page}: {url}")
                 
                 try:
                     response: httpx.Response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
                     if response.status_code == 404:
                         break
                         
                     # Decode
                     content: Optional[str] = None
                     encodings_to_try: List[str] = ['euc-jp', 'cp932', 'shift_jis', 'utf-8']
                     for encoding in encodings_to_try:
                        try:
                            content = response.content.decode(encoding)
                            break
                        except UnicodeDecodeError:
                            continue
                     
                     if not content:
                        content = response.content.decode('euc-jp', errors='replace')

                     soup: BeautifulSoup = BeautifulSoup(content, 'lxml')
                     item_elements: List[Tag] = soup.select('div.innerBox')
                     
                     if not item_elements:
                         break
                         
                     for item in item_elements:
                        p_item: Optional[ScrapedProduct] = extract_product_data(item)
                        if not p_item: continue
                        
                        product_url: str = p_item['url']
                        
                        if product_url in existing_urls:
                            consecutive_existing += 1
                        else:
                            consecutive_existing = 0
                        
                        all_items.append(p_item)
                        
                        if limit and len(all_items) >= limit:
                            print(f"[Chouseiya] Limit reached ({limit}). Stopping scan.")
                            stop_scan = True
                            break
                        
                        if consecutive_existing >= 30:
                           print(f"[Chouseiya] Found 30 consecutive existing items. Stopping scan.")
                           stop_scan = True
                           break
                     
                     if not stop_scan:
                         scan_page += 1
                              
                 except Exception as e:
                     print(f"[Chouseiya] Error scanning page {scan_page}: {e}")
                     break
            
             print(f"[Chouseiya] Smart Scrape Finished. Buffered {len(all_items)} items.")
             return all_items
        
        # Normal Mode
        page_num: int = 1
        while True:
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
                
                final_content: str = content if content else response.content.decode('euc-jp', errors='replace')
                soup = BeautifulSoup(final_content, 'lxml')

                item_elements = soup.select('div.innerBox')
                if not item_elements:
                    print(f"[Chouseiya] No items (div.innerBox) found on page {page_num}. Stopping.")
                    break
                
                page_items: List[ScrapedProduct] = []
                for item in item_elements:
                    p_item = extract_product_data(item)
                    if not p_item: continue
                    page_items.append(p_item)
                
                for p_item in page_items:
                    if p_item['stock_status'] == "Sold Out":
                        consecutive_sold_out += 1
                    else:
                        consecutive_sold_out = 0
                        
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
    items_list: List[ScrapedProduct] = asyncio.run(scrape_chouseiya(limit=5))
    print(items_list[:2])

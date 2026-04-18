import asyncio
import os
import re
import random
import requests
from typing import List, Dict, Optional, Set, Any
from bs4 import BeautifulSoup, Tag
import html
import time
from ..core.types import ScrapedProduct

# BeerVolta category base URLs (without page parameter)
CATEGORY_BASES: List[str] = [
    "https://beervolta.com/?mode=cate&cbid=2270431&csid=0&sort=n",  # ビール
    "https://beervolta.com/?mode=cate&cbid=2830081&csid=0&sort=n"   # ミード・シードル
]

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

# Headers to mimic a real browser to be safe
HEADERS: Dict[str, str] = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
}

def extract_product_data(item: Tag) -> Optional[ScrapedProduct]:
    """Helper to extract product data from a soup item."""
    try:
        href: Optional[str] = item.get('href')
        if not href:
            return None
        
        link: str
        if isinstance(href, str):
            if href.startswith('/'): link = f"https://beervolta.com{href}"
            elif href.startswith('http'): link = href
            else: link = f"https://beervolta.com/{href}"
        else:
            return None

        # Find the correct product image (skip icons)
        images: List[Tag] = item.find_all('img')
        img_tag: Optional[Tag] = None
        for img in images:
            classes: Any = img.get('class', [])
            src: Any = img.get('src', '')
            # Skip known icon classes or sources
            if 'new_mark_img' in str(classes) or 'icons' in str(src):
                continue
            img_tag = img
            break
        
        img_url: Optional[str] = None
        if img_tag:
            src_attr = img_tag.get('src')
            if isinstance(src_attr, str):
                img_url = src_attr
        
        # Name extraction strategy
        name_from_alt: str = ""
        if img_tag:
            alt_attr = img_tag.get('alt', '')
            if isinstance(alt_attr, str):
                name_from_alt = alt_attr.strip()
        
        text_content: str = item.get_text(strip=True, separator=' ')
        
        # Use alt if present and not generic
        name: str
        if name_from_alt and name_from_alt.lower() != 'unknown':
             name = name_from_alt
        else:
             name = text_content
             
        name = html.unescape(name)
        
        # Cleanup
        indicators: List[str] = ['≪12/10入荷予定≫', '≪入荷予定≫', '≪予約≫', '売切', 'SOLD OUT', 'SALE!!', 'SALE!']
        for indicator in indicators:
            name = name.replace(indicator, '').strip()
            
        # Remove price info from name if it leaked from text content
        name = re.sub(r'[0-9,]+円.*', '', name).strip()
        
        price: str = "Unknown"
        prices_found: List[str] = [part for part in item.get_text(strip=True, separator='|').split('|') if '円' in part]
        if prices_found:
            for price_str in prices_found:
                tax_match = re.search(r'[（(]税込([0-9,]+円)[）)]', price_str)
                if tax_match:
                    price = tax_match.group(1)
                    break
            else:
                price = prices_found[-1]

        stock_status: str = "In Stock"
        upper_text: str = text_content.upper()
        if '売切' in text_content or 'SOLD OUT' in upper_text:
            stock_status = "Sold Out"
        elif '入荷予定' in text_content: 
            stock_status = "Pre-order/Upcoming"
            
        if not img_url:
            return None
            
        return {
            "name": name,
            "price": price,
            "url": link,
            "image": img_url,
            "stock_status": stock_status,
            "shop": "BEER VOLTA"
        }
    except Exception as e:
        print(f"[Beervolta] Error parsing item: {e}")
        return None

async def scrape_beervolta(limit: Optional[int] = None, existing_urls: Optional[Set[str]] = None, full_scrape: bool = False) -> List[ScrapedProduct]:
    """
    Scrapes product data from Beervolta (Beer and Mead/Cider categories).
    Uses pagination to get all products.
    """
    all_products: List[ScrapedProduct] = []
    consecutive_sold_out: int = 0
    
    for i, category_base in enumerate(CATEGORY_BASES):
        # Check if we've reached the limit
        if limit and len(all_products) >= limit:
            break
        
        print(f"\n[Beervolta] Processing category: {category_base}")

        # Smart Mode Logic
        if existing_urls is not None:
            print(f"[Beervolta] New Product Scrape: Forward Scrape & Buffer...")
            
            scan_page: int = 1
            consecutive_existing: int = 0
            stop_scan: bool = False
            
            while not stop_scan:
                url: str = f"{category_base}&page={scan_page}" if scan_page > 1 else category_base
                print(f"[Beervolta] Smart Scrape {scan_page}: {url}")
                
                try:
                    response: requests.Response = requests.get(url, headers=HEADERS, timeout=30)
                    response.raise_for_status()
                    response.encoding = response.apparent_encoding or 'utf-8'
                    
                    await asyncio.sleep(random.uniform(0.3, 0.7)) # Be nice
                    
                    soup: BeautifulSoup = BeautifulSoup(response.content, 'lxml')
                    items: List[Tag] = soup.find_all('a', href=re.compile(r'\?pid='))
                    
                    if not items:
                        break
                        
                    seen_urls_page: Set[str] = set()
                    
                    for item in items:
                        p_item: Optional[ScrapedProduct] = extract_product_data(item)
                        if not p_item: continue
                        
                        link: str = p_item['url']
                        
                        if link in seen_urls_page: continue
                        seen_urls_page.add(link)
                        
                        if link in existing_urls:
                            consecutive_existing += 1
                        else:
                            consecutive_existing = 0
                        
                        if consecutive_existing >= 30:
                            print(f"[Beervolta] Found 30 consecutive existing items. Stopping scan.")
                            stop_scan = True
                            break
                            
                        all_products.append(p_item)
                        
                        if limit and len(all_products) >= limit:
                            print(f"[Beervolta] Limit reached ({limit}). Stopping scan.")
                            stop_scan = True
                            break
                    
                    if not stop_scan:
                        scan_page += 1
                            
                except Exception as e:
                    print(f"[Beervolta] Error scanning page {scan_page}: {e}")
                    break
                    
            continue # Move to next category

        # Normal Mode (if existing_urls is None)
        current_page: int = 1
        
        while True:
            # Check limit
            if limit and len(all_products) >= limit:
                break
            
            # Build URL with page parameter
            url = category_base if current_page == 1 else f"{category_base}&page={current_page}"
            
            print(f"[Beervolta] Scraping page {current_page}: {url}")
            
            # Random delay before navigation
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                response.encoding = response.apparent_encoding or 'utf-8'
                
            except Exception as e:
                print(f"[Beervolta] Error navigating to page {current_page}: {e}")
                break
            
            # Get page content
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Check if there are products on this page
            items = soup.find_all('a', href=re.compile(r'\?pid='))
            
            if not items:
                print(f"[Beervolta] No products found on page {current_page}. Stopping.")
                break
            
            print(f"[Beervolta] Found {len(items)} potential product links on page {current_page}")
            
            seen_urls = set()
            page_products: List[ScrapedProduct] = []
            
            for item in items:
                p_item = extract_product_data(item)
                if not p_item: continue
                
                link = p_item['url']
                if link in seen_urls: continue
                seen_urls.add(link)

                page_products.append(p_item)
                if p_item['stock_status'] == "Sold Out":
                    consecutive_sold_out += 1
                else:
                    consecutive_sold_out = 0
                
                all_products.append(p_item)
                if limit and len(all_products) >= limit: break
            
            if limit and len(all_products) >= limit: break
            
            if not full_scrape and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                print(f"[Beervolta] Stopping pagination due to consecutive sold-out items.")
                break
            
            print(f"[Beervolta] Extracted {len(page_products)} products from page {current_page}")

            if not page_products:
                print(f"[Beervolta] No products extracted from page {current_page}. Stopping.")
                break
            
            current_page += 1

    print(f"\n[Beervolta] Total extracted: {len(all_products)} products from all categories.")
    return all_products

if __name__ == "__main__":
    # For testing purposes
    import json
    data = asyncio.run(scrape_beervolta(limit=5))
    print(json.dumps(data[:5], indent=2, ensure_ascii=False))
    print(f"\nTotal: {len(data)} products")

if __name__ == "__main__":
    # For testing purposes
    import json
    data = asyncio.run(scrape_beervolta(limit=5))
    print(json.dumps(data[:5], indent=2, ensure_ascii=False))
    print(f"\nTotal: {len(data)} products")

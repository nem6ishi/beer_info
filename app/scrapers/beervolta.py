import asyncio
import os
import re
import random
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import html
import time

# BeerVolta category base URLs (without page parameter)
CATEGORY_BASES = [
    "https://beervolta.com/?mode=cate&cbid=2270431&csid=0&sort=n",  # ビール
    "https://beervolta.com/?mode=cate&cbid=2830081&csid=0&sort=n"   # ミード・シードル
]

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

# Headers to mimic a real browser to be safe
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
}

def extract_product_data(item) -> Optional[Dict[str, str]]:
    """Helper to extract product data from a soup item."""
    try:
        href = item.get('href', '')
        if not href: return None
        if href.startswith('/'): link = f"https://beervolta.com{href}"
        elif href.startswith('http'): link = href
        else: link = f"https://beervolta.com/{href}"

        img_tag = item.find('img')
        img_url = img_tag.get('src') if img_tag else None
        name = img_tag.get('alt', 'Unknown').strip() if img_tag else 'Unknown'
        name = html.unescape(name)
        for indicator in ['≪12/10入荷予定≫', '≪入荷予定≫', '≪予約≫', '売切', 'SOLD OUT']:
            name = name.replace(indicator, '').strip()
        
        text_content = item.get_text(strip=True, separator='|')
        parts = text_content.split('|')
        price = "Unknown"
        prices_found = [part for part in parts if '円' in part]
        if prices_found:
            for price_str in prices_found:
                tax_match = re.search(r'[（(]税込([0-9,]+円)[）)]', price_str)
                if tax_match:
                    price = tax_match.group(1)
                    break
            else:
                price = prices_found[-1]

        stock_status = "In Stock"
        upper_text = text_content.upper()
        if '売切' in text_content or 'SOLD OUT' in upper_text:
            stock_status = "Sold Out"
        elif '入荷予定' in text_content: 
            stock_status = "Pre-order/Upcoming"
            
        if not img_url:
            return None # Skip if no image (likely checks inside)
            
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

async def scrape_beervolta(limit: int = None, existing_urls: set = None, full_scrape: bool = False) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product data from Beervolta (Beer and Mead/Cider categories).
    Uses pagination to get all products.
    Uses requests for lightweight scraping (Playwright removed).
    Stops early if too many consecutive sold-out items are found, unless full_scrape is True.
    Returns a list of dictionaries containing product details.
    """
    all_products = []
    consecutive_sold_out = 0
    
    # Since we are running in an async function (scrape_to_supabase calls us with await),
    # but requests is synchronous, we can run it directly (blocking the event loop slightly is okay for this script)
    # or wrap it. Given the script structure, blocking is acceptable as it's running in parallel with other scrapers 
    # via asyncio.gather, but true parallelism would require running in an executor.
    # For simplicity and effectiveness, we'll execute the requests synchronously within this async function.
    # The asyncio.gather in scrape.py will wait for this function to complete.
    # To be truly non-blocking for other scrapers, we should ideally use aiohttp or run_in_executor.
    # However, since we are rewriting just this one, straightforward sync execution is fine 
    # as Python's asyncio is single-threaded anyway. The other scrapers might pause waiting for this CPU work,
    # but network wait is the main bottleneck.
    
    # Actually, to prevent blocking other concurrent scrapers (like Chouseiya), 
    # we should use asyncio.to_thread for the network calls or use aiohttp. 
    # Let's stick to requests but wrapping blocking calls is better practice.
    # But for now, direct requests is robust and simple.
    
    for i, category_base in enumerate(CATEGORY_BASES):
        # Check if we've reached the limit
        if limit and len(all_products) >= limit:
            break
        
        print(f"\n[Beervolta] Processing category: {category_base}")

        # Smart Mode Logic
        if existing_urls is not None:
            print(f"[Beervolta] Smart Mode: Forward Scrape & Buffer...")
            
            scan_page = 1
            consecutive_existing = 0
            stop_scan = False
            
            while not stop_scan:
                url = f"{category_base}&page={scan_page}" if scan_page > 1 else category_base
                print(f"[Beervolta] Smart Scrape {scan_page}: {url}")
                
                try:
                    # Sync request
                    response = requests.get(url, headers=HEADERS, timeout=30)
                    response.raise_for_status()
                    
                    # Beervolta uses EUC-JP encoding sometimes, but requests usually auto-detects.
                    # Explicitly set if needed, but usually .content + BeautifulSoup handles it.
                    # The curl output showed charset=EUC-JP.
                    response.encoding = response.apparent_encoding 
                    
                    await asyncio.sleep(random.uniform(0.3, 0.7)) # Be nice
                    
                    soup = BeautifulSoup(response.content, 'lxml')
                    items = soup.find_all('a', href=re.compile(r'\?pid='))
                    
                    if not items:
                        break
                        
                    seen_urls_page = set()
                    
                    for item in items:
                        p_item = extract_product_data(item)
                        if not p_item: continue
                        
                        link = p_item['url']
                        
                        if link in seen_urls_page: continue
                        seen_urls_page.add(link)
                        
                        if link in existing_urls:
                            consecutive_existing += 1
                        else:
                            consecutive_existing = 0
                            
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
                    
            continue # Move to next category (loop over categories)

        # Normal Mode (if existing_urls is None)
        current_page = 1
        
        while True:
            # Check limit
            if limit and len(all_products) >= limit:
                break
            
            # Build URL with page parameter
            if current_page == 1:
                url = category_base
            else:
                url = f"{category_base}&page={current_page}"
            
            print(f"[Beervolta] Scraping page {current_page}: {url}")
            
            # Random delay before navigation
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=30)
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                
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
            page_products = []
            
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
                
                if not full_scrape and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                        print(f"[Beervolta] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                        pass
                
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

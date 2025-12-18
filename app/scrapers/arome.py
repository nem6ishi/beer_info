import asyncio
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Optional
import concurrent.futures

# Early stop threshold for existing items
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '30'))

# Arome Search URL Template (Simplified)
SEARCH_URL_TEMPLATE = "https://www.arome.jp/products/list.php?category_id=0&disp_number=100&pageno={page}"
BASE_URL = "https://www.arome.jp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# Custom adapter to handle weak DH keys (DH_KEY_TOO_SMALL)
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_default_certs()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super(LegacySSLAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.load_default_certs()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super(LegacySSLAdapter, self).proxy_manager_for(*args, **kwargs)

def normalize_url(url: str) -> str:
    """Extracts product_id to ensure consistent URL matching."""
    if not url: return url
    match = re.search(r'product_id=(\d+)', url)
    if match:
        return f"{BASE_URL}/products/detail.php?product_id={match.group(1)}"
    return url

def extract_product_data(item, is_area=False) -> Optional[Dict]:
    """
    Parses a single product item from the list page.
    """
    try:
        if is_area:
            area = item
        else:
            area = item.select_one("div.gods_item")
        
        if not area:
            return None
            
        photo_div = area.select_one("div.listphoto")
        link_tag = None
        if photo_div:
            link_tag = photo_div.select_one('a')
            
        if not link_tag:
            return None
            
        relative_url = link_tag.get("href")
        product_url = urljoin(BASE_URL, relative_url)
        
        img_tag = link_tag.select_one("img")
        image_url = urljoin(BASE_URL, img_tag.get("src")) if img_tag else None

        right_div = area.select_one("div.listrightbloc")
        product_name = "Unknown"
        price = "Unknown"
        
        if right_div:
            name_link = right_div.select_one(f'a[href="{relative_url}"]')
            if not name_link:
                name_link = right_div.select_one('a')
            
            if name_link:
                from bs4.element import NavigableString
                name_parts = []
                for content in name_link.contents:
                    if content.name == 'br' or content.name == 'span':
                        break
                    if isinstance(content, NavigableString):
                        name_parts.append(str(content))
                
                product_name = "".join(name_parts).strip()
                
            elif img_tag and img_tag.get('alt'):
                 product_name = img_tag.get('alt')

            price_tag = right_div.select_one("span.price")
            if price_tag:
                raw_price = price_tag.get_text(strip=True)
                m_tax = re.search(r'税込[:：]\s*[¥￥]\s*([0-9,]+)', raw_price)
                if m_tax:
                    price = m_tax.group(1).replace(',', '') + "円"
                else:
                    m_simple = re.search(r'([0-9,]+)', raw_price)
                    if m_simple:
                        price = m_simple.group(1).replace(',', '') + "円"
                        
            if price == "Unknown":
                text = right_div.get_text()
                m = re.search(r'([0-9,]+)円', text)
                if not m:
                     m = re.search(r'[¥￥]\s*([0-9,]+)', text)
                if m:
                    price = m.group(1).replace(',', '') + "円"

        stock_status = "In Stock"
        text_zone = area.select_one("div.text-zone")
        if text_zone:
             zone_text = text_zone.get_text(strip=True)
             if "在庫切れ" in zone_text:
                 stock_status = "Sold Out"
            
        if stock_status == "In Stock":
            sold_out_img = area.select_one('img[alt="売り切れ"]') or area.select_one('img[src*="soldout"]')
            if sold_out_img:
                stock_status = "Sold Out"

        return {
            "name": product_name,
            "url": normalize_url(product_url),
            "price": price,
            "image": image_url,
            "stock_status": stock_status,
            "shop": "アローム"
        }

    except Exception as e:
        print(f"[Arome] Error parsing item: {e}")
        return None

def fetch_full_name(product_url) -> Optional[str]:
    """
    Fetches the detail page to get the full product name if truncated.
    NOTE: Thread-safe if each call uses its own session or a shared thread-safe session.
    We create a fresh session for safety/simplicity in threads or reuse a passed session?
    Requests sessions are thread-safe.
    """
    try:
        # Create a new session for thread safety and simplicity in concurrent futures
        session = requests.Session()
        session.mount("https://", LegacySSLAdapter())
        
        response = session.get(product_url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None
        
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        
        title_tag = soup.select_one("h2.productTitle") or soup.select_one("h2.title")
        if title_tag:
            return title_tag.get_text(strip=True)
            
        return None
    except Exception as e:
        print(f"[Arome] Error fetching detail: {e}")
        return None

async def scrape_arome(limit: int = None, existing_urls: set = None, full_scrape: bool = False) -> List[Dict]:
    products = []
    page = 1
    consecutive_existing = 0
    early_stop = False
    
    print(f"[Arome] Starting scrape...")
    if existing_urls is not None:
        print(f"[Arome] New product mode: Will stop after {SOLD_OUT_THRESHOLD} consecutive existing items")
    
    session = requests.Session()
    session.mount("https://", LegacySSLAdapter())
    
    while True:
        url = SEARCH_URL_TEMPLATE.format(page=page)
        print(f"[Arome] Scraping page {page}: {url}")
        
        try:
            # We must use asyncio.to_thread for the main page fetch to not block loop
            response = await asyncio.to_thread(session.get, url, headers=HEADERS, timeout=30)
            response.encoding = response.apparent_encoding
            
            if response.status_code != 200:
                print(f"[Arome] Failed to fetch page {page}. Status: {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title else "No Title"
            print(f"[Arome] Page Title: {title}")
            
            items = soup.select("div.list_area")
            if not items:
                print(f"[Arome] No items found on page {page}. Stopping.")
                break
            
            print(f"[Arome] Found {len(items)} items on page {page}.")
            
            # 1. Parse all items on page first
            page_products = []
            
            for area in items:
                product_data = extract_product_data(area, is_area=True)
                if product_data:
                    page_products.append(product_data)

            # 2. Identify items needing detail fetch (truncated names)
            tasks = []
            for p in page_products:
                name = p["name"]
                url = p["url"]
                is_existing = existing_urls is not None and url in existing_urls
                
                if (name.endswith("...") or name.endswith("…")):
                    if not is_existing:
                        # Add to list for parallel fetch
                        tasks.append(p)
                    else:
                        print(f"[Arome] Name truncated but item exists. Skipping detail fetch for: {url}")

            # 3. Parallel fetch using ThreadPool
            if tasks:
                print(f"[Arome] Fetching details for {len(tasks)} items in parallel...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    # Map urls to futures
                    future_to_product = {executor.submit(fetch_full_name, p["url"]): p for p in tasks}
                    
                    for future in concurrent.futures.as_completed(future_to_product):
                        p = future_to_product[future]
                        try:
                            full_name = future.result()
                            if full_name:
                                print(f"[Arome] Updated: {full_name[:50]}...")
                                p["name"] = full_name
                        except Exception as exc:
                            print(f"[Arome] Detail fetch failed for {p['url']}: {exc}")

            # 4. Add to main list and check limits
            for p in page_products:
                if limit and len(products) >= limit:
                    break
                
                is_existing = existing_urls is not None and p["url"] in existing_urls
                if existing_urls is not None:
                    if is_existing:
                        consecutive_existing += 1
                        if not full_scrape and consecutive_existing >= SOLD_OUT_THRESHOLD:
                            print(f"[Arome] ⚠️ Stopping: {consecutive_existing} consecutive existing items found.")
                            early_stop = True
                            # Don't break immediately, let's finish adding what we processed on this page?
                            # Or strict stop? Strict stop usually better.
                            products.append(p) # Add this one
                            break 
                    else:
                        consecutive_existing = 0

                products.append(p)
            
            if early_stop:
                break
            
            if limit and len(products) >= limit:
                print(f"[Arome] Limit reached ({limit}). Stopping.")
                break

            # Pagination check
            next_link = soup.find('a', string=re.compile("次へ"))
            if not next_link:
                next_link = soup.select_one(f'a[href*="pageno={page+1}"]')

            if not next_link:
                print(f"[Arome] No next page found. Stopping.")
                break
                
            page += 1
            await asyncio.sleep(1) 
            
        except Exception as e:
            print(f"[Arome] Error scraping page {page}: {e}")
            break
            
    print(f"[Arome] Finished! Scraped {len(products)} items.")
    return products

if __name__ == "__main__":
    import json
    # Simple test
    items = asyncio.run(scrape_arome(limit=5))
    print(json.dumps(items, indent=2, ensure_ascii=False))

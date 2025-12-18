import asyncio
import os
import re
import time
import requests
import ssl
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Optional
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_ as ssl_util

# Early stop threshold for existing items
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '30'))

# Arome Search URL Template (Simplified)
SEARCH_URL_TEMPLATE = "https://www.arome.jp/products/list.php?category_id=0&disp_number=100&pageno={page}"
BASE_URL = "https://www.arome.jp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

# Custom SSL Adapter to handle "DH key too small" error
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_util.create_urllib3_context(ciphers='DEFAULT:@SECLEVEL=1')
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=context
        )

def extract_product_data(item, is_area=False) -> Optional[Dict]:
    """
    Parses a single product item from the list page.
    """
    try:
        # 1. Detail URL & Image
        if is_area:
            area = item
        else:
            area = item.select_one("div.gods_item")
        
        if not area:
            return None
            
        # Structure for 'gods_item':
        # Image: div.listphoto > a > img
        # Name: div.listrightbloc > a (or inside)
        
        # 1. Image & URL
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

        # 2. Name & Price (in listrightbloc)
        right_div = area.select_one("div.listrightbloc")
        product_name = "Unknown"
        price = "Unknown"
        
        if right_div:
            # Name often in <h3> or directly in <a>
            # Let's try to find the link to detail?
            name_link = right_div.select_one(f'a[href="{relative_url}"]')
            if not name_link:
                # Try finding any link
                name_link = right_div.select_one('a')
            
            if name_link:
                # The <a> tag contains Name + <br> + Price.
                # We want only the text before the <br> or first text node.
                # Example: "Name <br> ¥ <span class="price">..."
                
                # Method 1: Get first text string
                # product_name = name_link.contents[0].strip() if name_link.contents else ""
                
                # Method 2: Iterate contents until <br> or tag
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

            # Price
            # Format: "708 (税込: ¥ 778)"
            price_tag = right_div.select_one("span.price")
            if price_tag:
                raw_price = price_tag.get_text(strip=True)
                # Try to find tax-inclusive price first
                m_tax = re.search(r'税込[:：]\s*[¥￥]\s*([0-9,]+)', raw_price)
                if m_tax:
                    price = m_tax.group(1).replace(',', '') + "円"
                else:
                    # Fallback: just grab the first number found
                    m_simple = re.search(r'([0-9,]+)', raw_price)
                    if m_simple:
                        price = m_simple.group(1).replace(',', '') + "円"
                        
            # Fallback price search
            if price == "Unknown":
                # Look for text with yen symbol?
                text = right_div.get_text()
                # Matches "1,100円" or "¥1,100"
                m = re.search(r'([0-9,]+)円', text)
                if not m:
                     m = re.search(r'[¥￥]\s*([0-9,]+)', text)
                
                if m:
                    price = m.group(1).replace(',', '') + "円"

        # 4. Stock Status
        # Check for red text "在庫切れ" in overlay
        # <div class="text-zone"><p style="text-align: center; color:red">在庫切れ</p></div>
        stock_status = "In Stock"
        
        # Check text zone
        text_zone = area.select_one("div.text-zone")
        if text_zone:
             zone_text = text_zone.get_text(strip=True)
             # print(f"[Arome] DEBUG - Stock Zone Text: '{zone_text}'")
             if "在庫切れ" in zone_text:
                 stock_status = "Sold Out"
            
        # Keep old checks just in case
        if stock_status == "In Stock":
            sold_out_img = area.select_one('img[alt="売り切れ"]') or area.select_one('img[src*="soldout"]')
            if sold_out_img:
                stock_status = "Sold Out"

        return {
            "name": product_name,
            "url": product_url,
            "price": price,
            "image": image_url,
            "stock_status": stock_status,
            "shop": "Arome"
        }

    except Exception as e:
        print(f"[Arome] Error parsing item: {e}")
        return None

def fetch_full_name(session, product_url) -> Optional[str]:
    """
    Fetches the detail page to get the full product name if truncated.
    """
    try:
        # print(f"[Arome] Fetching detail for full name: {product_url}")
        response = session.get(product_url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None
        
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Extracted from diagnostic: <h2 class="title productTitle">
        title_tag = soup.select_one("h2.productTitle") or soup.select_one("h2.title")
        if title_tag:
            return title_tag.get_text(strip=True)
            
        return None
    except Exception as e:
        print(f"[Arome] Error fetching detail: {e}")
        return None

async def scrape_arome(limit: int = None, existing_urls: set = None, full_scrape: bool = False) -> List[Dict]:
    """
    Scrapes products from Arome.
    Matches the signature of other scrapers for easy integration.
    
    Args:
        limit: Maximum number of items to scrape
        existing_urls: Set of existing URLs. If provided, tracks consecutive existing items.
        full_scrape: If True, ignore sold-out threshold and scrape everything.
    """
    products = []
    page = 1
    consecutive_existing = 0  # Track consecutive existing items
    early_stop = False
    
    print(f"[Arome] Starting scrape...")
    if existing_urls is not None:
        print(f"[Arome] New product mode: Will stop after {SOLD_OUT_THRESHOLD} consecutive existing items")
    
    # Create a session with the legacy SSL adapter
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    
    while True:
        url = SEARCH_URL_TEMPLATE.format(page=page)
        print(f"[Arome] Scraping page {page}: {url}")
        
        try:
            # Use the session for the request
            response = session.get(url, headers=HEADERS, timeout=30)
            response.encoding = response.apparent_encoding
            
            if response.status_code != 200:
                print(f"[Arome] Failed to fetch page {page}. Status: {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # DEBUG: Print title
            title = soup.title.string.strip() if soup.title else "No Title"
            print(f"[Arome] Page Title: {title}")
            
            # Items
            items = soup.select("div.list_area")
            
            if not items:
                print(f"[Arome] No items found on page {page}. Stopping.")
                break
                
            print(f"[Arome] Found {len(items)} items on page {page}.")
            
            for area in items:
                if limit and len(products) >= limit:
                    break

                product_data = extract_product_data(area, is_area=True)
                if product_data:
                    product_url = product_data["url"]
                    
                    # Check for truncated name - but skip if we already have this URL (re-scrape)
                    # because the DB already has the full name
                    name = product_data["name"]
                    is_existing = existing_urls is not None and product_url in existing_urls
                    
                    if (name.endswith("...") or name.endswith("…")) and not is_existing:
                        print(f"[Arome] Name truncated: '{name}'. Fetching detail...")
                        full_name = fetch_full_name(session, product_url)
                        if full_name:
                            print(f"[Arome] Updated name: '{full_name}'")
                            product_data["name"] = full_name
                        await asyncio.sleep(0.5) # Be polite when hitting details
                    
                    # Check if this is an existing item (for new product mode)
                    if existing_urls is not None:
                        if is_existing:
                            consecutive_existing += 1
                            # Check for early stop
                            if not full_scrape and consecutive_existing >= SOLD_OUT_THRESHOLD:
                                print(f"[Arome] ⚠️ Stopping: {consecutive_existing} consecutive existing items found.")
                                early_stop = True
                                break
                        else:
                            consecutive_existing = 0  # Reset counter on new item
                        
                    products.append(product_data)
            
            if early_stop:
                break
            
            if limit and len(products) >= limit:
                print(f"[Arome] Limit reached ({limit}). Stopping.")
                break

            # Pagination check
            # Check for "次へ>>" link
            next_link = soup.find('a', string=re.compile("次へ"))
            if not next_link:
                next_link = soup.select_one(f'a[href*="pageno={page+1}"]')

            if not next_link:
                print(f"[Arome] No next page found. Stopping.")
                break
                
            page += 1
            await asyncio.sleep(1) # Be polite
            
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

import asyncio
import copy
import os
import re
import ssl
import httpx
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin
from typing import List, Dict, Optional, Set, Any, cast
from ..core.types import ScrapedProduct

# Early stop threshold for existing items
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '30'))

# Arome Search URL Template (Simplified)
SEARCH_URL_TEMPLATE: str = "https://www.arome.jp/products/list.php?category_id=0&disp_number=100&pageno={page}"
BASE_URL: str = "https://www.arome.jp"

HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
}

def get_legacy_ssl_context() -> ssl.SSLContext:
    """Creates an SSLContext that allows legacy ciphers (SECLEVEL=1) for servers with weak DH keys."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers('DEFAULT@SECLEVEL=1')
    return ctx

def normalize_url(url: str) -> str:
    """Extracts product_id to ensure consistent URL matching."""
    if not url: return url
    match = re.search(r'product_id=(\d+)', url)
    if match:
        return f"{BASE_URL}/products/detail.php?product_id={match.group(1)}"
    return url

def extract_product_data(item: Tag, is_area: bool = False) -> Optional[ScrapedProduct]:
    """
    Parses a single product item from the list page.
    """
    try:
        area: Optional[Tag]
        if is_area:
            area = item
        else:
            area = item.select_one("div.gods_item")
        
        if not area:
            return None
            
        photo_div: Optional[Tag] = area.select_one("div.listphoto")
        link_tag: Optional[Tag] = None
        if photo_div:
            link_tag = photo_div.select_one('a')
            
        if not link_tag:
            return None
            
        relative_url: str = cast(str, link_tag.get("href", ""))
        product_url: str = urljoin(BASE_URL, relative_url)
        
        img_tag: Optional[Tag] = link_tag.select_one("img")
        image_url: Optional[str] = urljoin(BASE_URL, cast(str, img_tag.get("src", ""))) if img_tag else None

        right_div: Optional[Tag] = area.select_one("div.listrightbloc")
        product_name: str = "Unknown"
        price: str = "Unknown"
        
        if right_div:
            name_link: Optional[Tag] = right_div.select_one(f'a[href="{relative_url}"]')
            if not name_link:
                name_link = right_div.select_one('a')
            
            if name_link:
                link_copy = copy.copy(name_link)
                for p_el in link_copy.select(".price, span[id^='price02_'], p.price"):
                    p_el.decompose()
                product_name = link_copy.get_text(strip=True)
                if product_name.endswith("¥") or product_name.endswith("￥"):
                    product_name = product_name[:-1].strip()
                
            price_tag: Optional[Tag] = right_div.select_one(".price") or right_div.select_one("span[id^='price02_']") or right_div.select_one("p.price")
            if price_tag:
                raw_price: str = price_tag.get_text(strip=True)
                m = re.search(r'税込:\s*[¥￥]?\s*([0-9,]+)', raw_price)
                if m:
                    clean_num = re.sub(r'[^0-9]', '', m.group(1))
                    price = f"{clean_num}円"
                else:
                    m2 = re.search(r'([0-9,]+)', raw_price)
                    if m2:
                        clean_num = re.sub(r'[^0-9]', '', m2.group(1))
                        price = f"{clean_num}円"
                    else:
                        price = raw_price

        stock_status: str = "In Stock"
        if area.select_one("p.soldout") or area.select_one("img[src*='soldout']"):
            stock_status = "Sold Out"
        if "sold out" in area.get_text().lower() or "売切" in area.get_text():
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

async def fetch_product_detail(client: httpx.AsyncClient, product_url: str, sem: Optional[asyncio.Semaphore] = None) -> Optional[Dict[str, str]]:
    """
    Fetches the detail page to get the full product name and tax-included price if needed.
    """
    try:
        if sem:
            await sem.acquire()
        try:
            response: httpx.Response = await client.get(product_url, timeout=30.0)
        finally:
            if sem:
                sem.release()
        if response.status_code != 200:
            return None
        
        response.encoding = response.encoding or 'utf-8'
        soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
        
        result: Dict[str, str] = {}
        title_tag: Optional[Tag] = soup.select_one("h2.productTitle") or soup.select_one("h2.title")
        if title_tag:
            clean_title = title_tag.get_text(strip=True)
            clean_title = re.sub(r'¥[0-9,]+.*$', '', clean_title).strip()
            result["name"] = clean_title
            
        sale_p = soup.select_one("p.sale_price")
        if sale_p:
            raw_price = sale_p.get_text(strip=True)
            m = re.search(r'税込:\s*[¥￥]?\s*([0-9,]+)', raw_price)
            if not m:
                m = re.search(r'([0-9,]+)', raw_price)
            if m:
                clean_num = re.sub(r'[^0-9]', '', m.group(1))
                result["price"] = f"{clean_num}円"
                
        return result if result else None
    except Exception as e:
        print(f"[Arome] Error fetching detail: {e}")
        return None

async def scrape_arome(limit: Optional[int] = None, existing_urls: Optional[Set[str]] = None, full_scrape: bool = False) -> List[ScrapedProduct]:
    """Scrapes product data from Arome."""
    products: List[ScrapedProduct] = []
    page: int = 1
    consecutive_existing: int = 0
    early_stop: bool = False
    
    print(f"[Arome] Starting scrape...")
    if existing_urls is not None:
        print(f"[Arome] New product mode: Will stop after {SOLD_OUT_THRESHOLD} consecutive existing items")
    
    ssl_ctx = get_legacy_ssl_context()
    async with httpx.AsyncClient(verify=ssl_ctx, headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        while True:
            url: str = SEARCH_URL_TEMPLATE.format(page=page)
            print(f"[Arome] Scraping page {page}: {url}")
            
            try:
                response: httpx.Response = await client.get(url)
                response.encoding = response.encoding or 'utf-8'
                
                if response.status_code != 200:
                    print(f"[Arome] Failed to fetch page {page}. Status: {response.status_code}")
                    break
                    
                soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
                
                items: List[Tag] = soup.select("div.list_area")
                if not items:
                    print(f"[Arome] No items found on page {page}. Stopping.")
                    break
                
                print(f"[Arome] Found {len(items)} items on page {page}.")
                
                # 1. Parse all items on page first
                page_products: List[ScrapedProduct] = []
                
                for area in items:
                    product_data: Optional[ScrapedProduct] = extract_product_data(area, is_area=True)
                    if product_data:
                        page_products.append(product_data)

                # 2. Identify items needing detail fetch (truncated names or unknown prices)
                tasks: List[ScrapedProduct] = []
                for p in page_products:
                    name: str = p["name"]
                    p_url: str = p["url"]
                    is_existing: bool = existing_urls is not None and p_url in existing_urls
                    
                    needs_detail = (name.endswith("...") or name.endswith("…") or p["price"] == "Unknown" or "¥" in name or "￥" in name)
                    if needs_detail:
                        if not is_existing or p["price"] == "Unknown" or "¥" in name or "￥" in name:
                            tasks.append(p)
                        else:
                            print(f"[Arome] Name truncated but item exists and looks valid. Skipping detail fetch for: {p_url}")

                # 3. Parallel fetch using asyncio.gather
                if tasks:
                    print(f"[Arome] Fetching details for {len(tasks)} items with concurrency control...")
                    sem: asyncio.Semaphore = asyncio.Semaphore(10)
                    detail_results = await asyncio.gather(
                        *[fetch_product_detail(client, p["url"], sem) for p in tasks],
                        return_exceptions=True
                    )
                    for p, res in zip(tasks, detail_results):
                        if isinstance(res, dict) and res:
                            if "name" in res and res["name"]:
                                p["name"] = res["name"]
                            if "price" in res and res["price"] and (p["price"] == "Unknown" or p["price"] == "0円"):
                                p["price"] = res["price"]
                        elif isinstance(res, Exception):
                            print(f"[Arome] Detail fetch failed for {p['url']}: {res}")

                # 4. Add to main list and check limits
                for p in page_products:
                    if limit and len(products) >= limit:
                        break
                    
                    p_url = p["url"]
                    is_existing = existing_urls is not None and p_url in existing_urls
                    if existing_urls is not None:
                        if is_existing:
                            consecutive_existing += 1
                            if not full_scrape and consecutive_existing >= SOLD_OUT_THRESHOLD:
                                print(f"[Arome] ⚠️ Stopping: {consecutive_existing} consecutive existing items found.")
                                early_stop = True
                                products.append(p)
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
                next_link: Optional[Tag] = soup.find('a', string=re.compile("次へ"))
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
    items: List[ScrapedProduct] = asyncio.run(scrape_arome(limit=5))
    print(json.dumps(items, indent=2, ensure_ascii=False))

import asyncio
import os
import httpx
from bs4 import BeautifulSoup, Tag
from typing import List, Dict, Optional, Set, Any, Union
import time
import re
from ..core.types import ScrapedProduct

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
# Number of pages to fetch in parallel
BATCH_SIZE: int = 10

class FetchResult(Dict[str, Any]):
    """Result of a single page fetch."""
    page_num: int
    status: int
    content: Optional[bytes]
    error: Optional[str]

async def fetch_page(client: httpx.AsyncClient, url: str, page_num: int) -> FetchResult:
    """
    Fetches a single page and returns the result with page number for sorting.
    """
    try:
        response: httpx.Response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
        return FetchResult(
            page_num=page_num,
            status=response.status_code,
            content=response.content,
            error=None
        )
    except Exception as e:
        return FetchResult(
            page_num=page_num,
            status=0,
            content=None,
            error=str(e)
        )

def parse_page_content(content: Optional[bytes], selector: str = 'li.productlist_list') -> List[ScrapedProduct]:
    """
    Parses HTML content and returns a list of product dictionaries.
    """
    if not content:
        return []

    # Decode content
    decoded_html: Optional[str] = None
    encodings: List[str] = ['euc-jp', 'shift_jis', 'utf-8']
    for enc in encodings:
        try:
            decoded_html = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    
    if not decoded_html:
        decoded_html = content.decode('utf-8', errors='replace')

    soup: BeautifulSoup = BeautifulSoup(decoded_html, 'lxml')
    items: List[Tag] = soup.select(selector)
    
    if not items:
        # Fallback: try finding .recommend_list if default selector failed
        if selector == 'li.productlist_list':
             items = soup.select('li.recommend_list')
    
    if not items:
        return []

    page_items: List[ScrapedProduct] = []
    
    for item in items:
        try:
            link_tag: Optional[Tag] = item.find('a')
            if not link_tag: continue
            
            href: Any = link_tag.get('href', '')
            if not isinstance(href, str): href = ""
            
            product_url: str = f"https://151l.shop/{href}" if not href.startswith('http') else href
            
            img_tag: Optional[Tag] = item.select_one('img.item_img')
            image_url: Optional[str] = None
            img_alt: str = ""
            if img_tag:
                src_attr: Any = img_tag.get('src', '')
                if isinstance(src_attr, str):
                    image_url = src_attr if src_attr.startswith('http') else f"https://151l.shop{src_attr}"
                
                alt_attr: Any = img_tag.get('alt', '')
                if isinstance(alt_attr, str):
                    img_alt = alt_attr.strip()

            name: str = "Unknown"
            name_tag: Optional[Tag] = item.select_one('span.item_name')
            if name_tag: 
                name = name_tag.get_text(strip=True)
            elif img_alt:
                name = img_alt

            price: str = "Unknown"
            price_tag: Optional[Tag] = item.select_one('span.item_price')
            if price_tag:
                raw_price: str = price_tag.get_text(strip=True)
                match = re.search(r'税込([0-9,]+円)', raw_price)
                if match: price = match.group(1)
                else: price = raw_price
            
            stock_status: str = "In Stock"
            if "SOLD OUT" in item.get_text().upper():
                    stock_status = "Sold Out"
            
            p_item: ScrapedProduct = {
                "name": name,
                "price": price,
                "url": product_url,
                "image": image_url,
                "stock_status": stock_status,
                "shop": "一期一会～る"
            }
            page_items.append(p_item)

        except Exception as e:
            print(f"[Ichigo Ichie] Error parsing item: {e}")
            continue
            
    return page_items

async def scrape_ichigo_ichie(limit: Optional[int] = None, existing_urls: Optional[Set[str]] = None, full_scrape: bool = False) -> List[ScrapedProduct]:
    """
    Scrapes product information from Ichigo Ichie (https://151l.shop/).
    Uses batched parallel requests to speed up scraping.
    """
    top_url: str = "https://151l.shop/"
    base_url: str = "https://151l.shop/?mode=grp&gid=1978037&sort=n&page={}"
    products: List[ScrapedProduct] = []
    seen_urls: Set[str] = set()
    consecutive_sold_out: int = 0
    consecutive_existing: int = 0
    
    async with httpx.AsyncClient() as client:
        # Phase 1: Top Page (ONLY in New Product Scrape mode)
        if existing_urls is not None:
            print(f"[Ichigo Ichie] New Product Scrape: Scraping Top Page ({top_url}) ONLY...")
            try:
                top_res: FetchResult = await fetch_page(client, top_url, 0)
                if top_res['status'] == 200 and not top_res['error']:
                    top_items: List[ScrapedProduct] = parse_page_content(top_res['content'], selector='li.recommend_list')
                    print(f"[Ichigo Ichie] Top Page found {len(top_items)} items")
                    for item in top_items:
                        if item['url'] not in seen_urls:
                            products.append(item)
                            seen_urls.add(item['url'])
                            if limit and len(products) >= limit:
                                return products
                else:
                    print(f"[Ichigo Ichie] Failed to fetch Top Page: {top_res.get('error') or top_res['status']}")
            except Exception as e:
                print(f"[Ichigo Ichie] Error scraping Top Page: {e}")
            
            print(f"[Ichigo Ichie] New Product Scrape Completed. Extracted {len(products)} products.")
            return products

        # Phase 2: Category Pages
        print(f"[Ichigo Ichie] Normal/Full Scrape: Scraping Category Pages...")
        current_page: int = 1
        stop_scan: bool = False
        
        while not stop_scan:
            tasks = []
            for i in range(BATCH_SIZE):
                page_num = current_page + i
                url = base_url.format(page_num)
                tasks.append(fetch_page(client, url, page_num))
            
            print(f"[Ichigo Ichie] Fetching pages {current_page} to {current_page + BATCH_SIZE - 1}...")
            
            results: List[FetchResult] = await asyncio.gather(*tasks)
            
            for result in results:
                page_num = result['page_num']
                
                if result['error'] or result['status'] != 200:
                    print(f"[Ichigo Ichie] Error or non-200 status on page {page_num}. Stopping.")
                    stop_scan = True
                    break
                
                page_items = parse_page_content(result['content'])
                if not page_items:
                    print(f"[Ichigo Ichie] No items found on page {page_num}. Stopping.")
                    stop_scan = True
                    break
                
                print(f"[Ichigo Ichie] Page {page_num}: Found {len(page_items)} items")
                
                for p_item in page_items:
                    if p_item['url'] in seen_urls:
                        continue
                    seen_urls.add(p_item['url'])

                    if existing_urls is not None:
                        if p_item['url'] in existing_urls:
                            consecutive_existing += 1
                        else:
                            consecutive_existing = 0
                            
                        if consecutive_existing >= 30:
                             print(f"[Ichigo Ichie] Found 30 consecutive existing items. Stopping scan.")
                             stop_scan = True
                             break
                    
                    if p_item['stock_status'] == "Sold Out":
                        consecutive_sold_out += 1
                    else:
                        consecutive_sold_out = 0
                    
                    if existing_urls is None and not full_scrape and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                         print(f"[Ichigo Ichie] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                         stop_scan = True
                         break
                    
                    products.append(p_item)
                    if limit and len(products) >= limit:
                        stop_scan = True
                        break
                
                if stop_scan:
                    break
            
            if limit and len(products) >= limit or stop_scan:
                break
                
            current_page += BATCH_SIZE
            await asyncio.sleep(0.5)

    print(f"[Ichigo Ichie] Extracted {len(products)} products.")
    return products

if __name__ == "__main__":
    import json
    start_time: float = time.time()
    data: List[ScrapedProduct] = asyncio.run(scrape_ichigo_ichie(limit=20))
    end_time: float = time.time()
    print(json.dumps(data[:3], indent=2, ensure_ascii=False))
    print(f"Total time: {end_time - start_time:.2f} seconds")


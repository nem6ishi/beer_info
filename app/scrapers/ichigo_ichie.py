import asyncio
import os
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import time
import re

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
# Number of pages to fetch in parallel
BATCH_SIZE = 10

async def fetch_page(client: httpx.AsyncClient, url: str, page_num: int) -> Dict:
    """
    Fetches a single page and returns the result with page number for sorting.
    """
    try:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
        return {
            "page_num": page_num,
            "status": response.status_code,
            "content": response.content,
            "error": None
        }
    except Exception as e:
        return {
            "page_num": page_num,
            "status": 0,
            "content": None,
            "error": str(e)
        }

def parse_page_content(content: bytes, selector: str = 'li.productlist_list') -> List[Dict]:
    """
    Parses HTML content and returns a list of product dictionaries.
    """
    if not content:
        return []

    # Decode content
    decoded_html = None
    encodings = ['euc-jp', 'shift_jis', 'utf-8']
    for enc in encodings:
        try:
            decoded_html = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not decoded_html:
        decoded_html = content.decode('utf-8', errors='replace')

    soup = BeautifulSoup(decoded_html, 'lxml')
    items = soup.select(selector)
    
    if not items:
        # Fallback: try finding .recommend_list if default selector failed and we didn't specify one
        if selector == 'li.productlist_list':
             items = soup.select('li.recommend_list')
    
    if not items:
        return []

    page_items = []
    
    for item in items:
        try:
            # Parsing logic
            link_tag = item.find('a')
            if not link_tag: continue
            href = link_tag.get('href', '')
            product_url = f"https://151l.shop/{href}" if not href.startswith('http') else href
            
            img_tag = item.select_one('img.item_img')
            image_url = None
            img_alt = None
            if img_tag:
                src = img_tag.get('src', '')
                image_url = src if src.startswith('http') else f"https://151l.shop{src}"
                img_alt = img_tag.get('alt', '').strip()

            name = "Unknown"
            name_tag = item.select_one('span.item_name')
            if name_tag: 
                name = name_tag.get_text(strip=True)
            elif img_alt:
                # Fallback to img alt if name tag is missing (common in Top Page recommend_list)
                name = img_alt

            price = "Unknown"
            price_tag = item.select_one('span.item_price')
            if price_tag:
                raw_price = price_tag.get_text(strip=True)
                match = re.search(r'税込([0-9,]+円)', raw_price)
                if match: price = match.group(1)
                else: price = raw_price
            
            stock_status = "In Stock"
            if "SOLD OUT" in item.get_text().upper():
                    stock_status = "Sold Out"
            
            p_item = {
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

async def scrape_ichigo_ichie(limit: int = None, existing_urls: set = None, full_scrape: bool = False) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product information from Ichigo Ichie (https://151l.shop/).
    Uses batched parallel requests to speed up scraping while maintaining order.
    """
    top_url = "https://151l.shop/"
    base_url = "https://151l.shop/?mode=grp&gid=1978037&sort=n&page={}"  # 全てのビール一覧
    products = []
    seen_urls = set()
    consecutive_sold_out = 0
    consecutive_existing = 0
    
    async with httpx.AsyncClient() as client:
        # Phase 1: Top Page (ONLY in New Product Scrape mode)
        if existing_urls is not None:
            print(f"[Ichigo Ichie] New Product Scrape: Scraping Top Page ({top_url}) ONLY...")
            try:
                # We reuse fetch_page but page_num is 0 for top page
                top_res = await fetch_page(client, top_url, 0)
                if top_res['status'] == 200 and not top_res['error']:
                    # Use selector for Top Page recommendation list
                    top_items = parse_page_content(top_res['content'], selector='li.recommend_list')
                    print(f"[Ichigo Ichie] Top Page found {len(top_items)} items")
                    for item in top_items:
                        if item['url'] not in seen_urls:
                            products.append(item)
                            seen_urls.add(item['url'])
                            if limit and len(products) >= limit:
                                print(f"[Ichigo Ichie] Limit reached ({limit}) in Phase 1. Stopping.")
                                return products # Stop completely
                else:
                    print(f"[Ichigo Ichie] Failed to fetch Top Page: {top_res.get('error') or top_res['status']}")
            except Exception as e:
                print(f"[Ichigo Ichie] Error scraping Top Page: {e}")
            
            # In New Mode, we STOP here as requested
            print(f"[Ichigo Ichie] New Product Scrape Completed. Extracted {len(products)} products.")
            return products

        # Phase 2: Category Pages (ONLY in Normal/Full Mode)
        print(f"[Ichigo Ichie] Normal/Full Scrape: Scraping Category Pages...")
        current_page = 1
        stop_scan = False
        
        mode_label = "New Product Scrape" if existing_urls is not None else "Normal Mode"
        if existing_urls is not None:
             print(f"[Ichigo Ichie] {mode_label}: Forward Scrape & Buffer...")
        
        while not stop_scan:
            # Prepare batch of tasks
            tasks = []
            for i in range(BATCH_SIZE):
                page_num = current_page + i
                url = base_url.format(page_num)
                tasks.append(fetch_page(client, url, page_num))
            
            print(f"[Ichigo Ichie] Fetching pages {current_page} to {current_page + BATCH_SIZE - 1}...")
            
            # Execute batch
            results = await asyncio.gather(*tasks)
            
            # Process results in order
            # The results list corresponds to the tasks list order, so it is already sorted by page_num
            for result in results:
                page_num = result['page_num']
                
                if result['error']:
                    print(f"[Ichigo Ichie] Error on page {page_num}: {result['error']}. Stopping.")
                    stop_scan = True
                    break
                
                if result['status'] != 200:
                    print(f"[Ichigo Ichie] Page {page_num} returned status {result['status']}. Stopping.")
                    stop_scan = True
                    break
                
                # Parse content
                page_items = parse_page_content(result['content'])
                
                if not page_items:
                    print(f"[Ichigo Ichie] No items found on page {page_num}. Stopping.")
                    stop_scan = True
                    break
                
                print(f"[Ichigo Ichie] Page {page_num}: Found {len(page_items)} items")
                
                # Process items strictly in order
                for p_item in page_items:
                    # Skip if saw in Top Page
                    if p_item['url'] in seen_urls:
                        continue
                    seen_urls.add(p_item['url'])

                    # Logic checks
                    
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
                    
                    # Stop conditions
                    # In New Product Scrape mode (existing_urls is not None), we ONLY stop based on existing_urls count.
                    # We ignore consecutive_sold_out in that mode.
                    if existing_urls is None and not full_scrape and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                         print(f"[Ichigo Ichie] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                         stop_scan = True
                         break
                    
                    products.append(p_item)
                    
                    if limit and len(products) >= limit:
                        print(f"[Ichigo Ichie] Limit reached ({limit}). Stopping.")
                        stop_scan = True
                        break
                
                if stop_scan:
                    break
            
            # Global limit check (after batch)
            if limit and len(products) >= limit:
                break

            if stop_scan:
                break
                
            current_page += BATCH_SIZE
            await asyncio.sleep(0.5) # Be nice to the server between batches

    print(f"[Ichigo Ichie] Extracted {len(products)} products.")
    return products

if __name__ == "__main__":
    import json
    # Test run
    start_time = time.time()
    data = asyncio.run(scrape_ichigo_ichie(limit=20))
    end_time = time.time()
    print(json.dumps(data[:3], indent=2, ensure_ascii=False))
    print(f"Total time: {end_time - start_time:.2f} seconds")


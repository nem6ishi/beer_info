import asyncio
import os
import re
import random
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import html

# BeerVolta category base URLs (without page parameter)
CATEGORY_BASES = [
    "https://beervolta.com/?mode=cate&cbid=2270431&csid=0&sort=n",  # ビール
    "https://beervolta.com/?mode=cate&cbid=2830081&csid=0&sort=n"   # ミード・シードル
]

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))

async def scrape_beervolta(limit: int = None, reverse: bool = False, start_page_hint: int = None, existing_urls: set = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product data from Beervolta (Beer and Mead/Cider categories).
    Uses pagination to get all products.
    Includes anti-bot protection measures.
    Stops early if too many consecutive sold-out items are found (DISABLED if reverse=True).
    Returns a list of dictionaries containing product details.
    """
    all_products = []
    consecutive_sold_out = 0
    
    async with async_playwright() as p:
        # Launch browser with stealth settings
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        
        # Create context with realistic settings
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ja-JP',
            timezone_id='Asia/Tokyo'
        )
        
        page = await context.new_page()
        
        # Override navigator.webdriver
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = { runtime: {} };
        """)
        
        primary_max_page = None
        
        for i, category_base in enumerate(CATEGORY_BASES):
            # Check if we've reached the limit
            if limit and len(all_products) >= limit:
                break
            
            print(f"\n[Beervolta] Processing category: {category_base}")
            
            if existing_urls is not None:
                # Phase 1: Forward Scrape & Buffer
                print(f"[Beervolta] Smart Mode: Forward Scrape & Buffer...")
                
                scan_page = 1
                consecutive_existing = 0
                stop_scan = False
                
                while not stop_scan:
                    url = f"{category_base}&page={scan_page}" if scan_page > 1 else category_base
                    print(f"[Beervolta] Smart Scrape {scan_page}: {url}")
                    
                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(random.uniform(0.3, 0.7))
                        
                        content = await page.content()
                        soup = BeautifulSoup(content, 'lxml')
                        items = soup.find_all('a', href=re.compile(r'\?pid='))
                        
                        if not items:
                            break
                            
                        seen_urls_page = set()
                        
                        for item in items:
                            href = item.get('href', '')
                            if not href: continue
                            if href.startswith('/'): link = f"https://beervolta.com{href}"
                            elif href.startswith('http'): link = href
                            else: link = f"https://beervolta.com/{href}"
                            
                            if link in seen_urls_page: continue
                            seen_urls_page.add(link)
                            
                            if link in existing_urls:
                                consecutive_existing += 1
                            else:
                                consecutive_existing = 0
                                
                            # Parse Item Details
                            try:
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
                                    
                                p_item = {
                                    "name": name,
                                    "price": price,
                                    "url": link,
                                    "image": img_url,
                                    "stock_status": stock_status,
                                    "shop": "BEER VOLTA"
                                }
                                
                                all_products.append(p_item)
                                
                                if limit and len(all_products) >= limit:
                                    print(f"[Beervolta] Limit reached ({limit}). Stopping scan.")
                                    stop_scan = True
                                    break
                                
                                if consecutive_existing >= 10:
                                    print(f"[Beervolta] Found 10 consecutive existing items. Stopping scan.")
                                    stop_scan = True
                                    break
                                    
                            except Exception as e:
                                print(f"[Beervolta] Error parsing item: {e}")
                                continue
                        
                        if not stop_scan:
                            scan_page += 1
                            if scan_page > 50: 
                                print("[Beervolta] Scan limit reached (50 pages). Stopping probe.")
                                break
                                
                    except Exception as e:
                        print(f"[Beervolta] Error scanning page {scan_page}: {e}")
                        break
                        
                continue # Move to next category (loop over categories)

            max_pages = 100
            step = 1
            end_page_limit = 1 # Default stop for reverse scan (exclusive? < limit)
            
            if reverse:
                print("[Beervolta] Reverse mode: Finding last page...")
                
                # Optimization: Check if hint+1 exists first (Only for first category)
                skip_scan = False
                if i == 0 and start_page_hint and start_page_hint > 0:
                    print(f"[Beervolta] checking hint+1 ({start_page_hint + 1})")
                    try:
                        probe_url = f"{category_base}&page={start_page_hint + 1}"
                        # Use raw request for speed if possible, or just page.goto since we have browser open
                        await page.goto(probe_url, wait_until='domcontentloaded', timeout=15000)
                        content = await page.content()
                        soup_probe = BeautifulSoup(content, 'lxml')
                        items_probe = soup_probe.find_all('a', href=re.compile(r'\?pid='))
                        
                        if not items_probe:
                             print(f"[Beervolta] No items on page {start_page_hint + 1}. Keeping max page as {start_page_hint}.")
                             max_page_found = start_page_hint
                             start_page = start_page_hint
                             skip_scan = True
                             # Ensure loop doesn't run excessively
                             max_pages = 0
                             step = -1
                             # Also set end_page_limit for the loop below
                             end_page_limit = start_page_hint
                        else:
                             print(f"[Beervolta] Found items on {start_page_hint + 1}. Rescanning from Page 1.")
                    except Exception as e:
                        print(f"[Beervolta] Probe failed: {e}. Proceeding with full scan.")

                if not skip_scan:
                    try:
                        # Goto page 1
                        await page.goto(category_base, wait_until='domcontentloaded', timeout=30000)
                        
                        # Look for pagination links
                        # Typically looks like <div class="pager">... <a href="...">X</a> </div>
                        # We can use regex on hrefs or just scan the numbers
                        content = await page.content()
                        soup = BeautifulSoup(content, 'lxml')
                        max_page_found = 1
                        
                        # Beervolta uses query params &page=X
                        links = soup.find_all('a', href=re.compile(r'page=\d+'))
                        for link in links:
                            match = re.search(r'page=(\d+)', link.get('href', ''))
                            if match:
                                p_num = int(match.group(1))
                                if p_num > max_page_found:
                                    max_page_found = p_num
                        
                        print(f"[Beervolta] Detected last page: {max_page_found}")
                        if i == 0:
                            primary_max_page = max_page_found
                        start_page = max_page_found
                        max_pages = 0 # Loop until < 1, handled by range
                        step = -1
                        
                        if start_page_hint and start_page_hint > 0:
                            # Scrape down to hint. 
                            end_page_limit = start_page_hint
                            print(f"[Beervolta] Incremental mode: Scraping from {start_page} down to {start_page_hint}...")
                        else:
                            end_page_limit = 1
                        
                    except Exception as e:
                         print(f"[Beervolta] Error finding last page: {e}. Defaulting to normal.")
                         reverse = False
                         start_page = 1
                         max_pages = 100
                         step = 1
                         end_page_limit = 1
            
            # Determine loop range. If reverse, we cant easily use while loop structure same way without counter
            # Easier to use 'current_page' variable
            current_page = start_page
            
            while True:
                # Loop condition
                if not reverse:
                    if current_page > max_pages: break
                else:
                    if current_page < end_page_limit: break

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
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    
                except Exception as e:
                    print(f"[Beervolta] Error navigating to page {current_page}: {e}")
                    if reverse:
                        current_page += step
                        continue
                    else:
                        break
                
                # Get page content
                content = await page.content()
                soup = BeautifulSoup(content, 'lxml')
                
                # Check if there are products on this page
                items = soup.find_all('a', href=re.compile(r'\?pid='))
                
                if not items:
                    if not reverse:
                        print(f"[Beervolta] No products found on page {current_page}. Stopping.")
                        break
                    else:
                         # In reverse, maybe gaps? or end of list? 
                         print(f"[Beervolta] No products on page {current_page}.")
                
                print(f"[Beervolta] Found {len(items)} potential product links on page {current_page}")
                
                seen_urls = set()
                page_products = []
                
                for item in items:
                    try:
                        href = item.get('href', '')
                        if not href: continue
                        if href.startswith('/'): link = f"https://beervolta.com{href}"
                        elif href.startswith('http'): link = href
                        else: link = f"https://beervolta.com/{href}"
                        
                        if link in seen_urls: continue
                        seen_urls.add(link)

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

                        if img_url: 
                            page_products.append({
                                "name": name,
                                "price": price,
                                "url": link,
                                "image": img_url,
                                "stock_status": stock_status,
                                "shop": "BEER VOLTA"
                            })

                    except Exception as e:
                        print(f"[Beervolta] Error parsing item: {e}")
                        continue
                
                # Reverse items if needed
                if reverse:
                    page_products.reverse()
                
                for p in page_products:
                    # Sold out logic ONLY if not reverse
                    if not reverse:
                        if p['stock_status'] == "Sold Out":
                            consecutive_sold_out += 1
                        else:
                            consecutive_sold_out = 0
                        
                        if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                             print(f"[Beervolta] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                             # break? pass?
                             pass
                    
                    all_products.append(p)
                    if limit and len(all_products) >= limit: break
                
                if limit and len(all_products) >= limit: break
                
                if not reverse and consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Beervolta] Stopping pagination due to consecutive sold-out items.")
                    break
                
                print(f"[Beervolta] Extracted {len(page_products)} products from page {current_page}")

                if not reverse and not page_products:
                    print(f"[Beervolta] No products extracted from page {current_page}. Stopping.")
                    break
                
                current_page += step

        
        await context.close()
        await browser.close()

    print(f"\n[Beervolta] Total extracted: {len(all_products)} products from all categories.")
    return all_products, primary_max_page

if __name__ == "__main__":
    # For testing purposes
    import json
    data = asyncio.run(scrape_beervolta())
    print(json.dumps(data[:5], indent=2, ensure_ascii=False))  # Show first 5
    print(f"\nTotal: {len(data)} products")

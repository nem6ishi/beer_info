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

async def scrape_beervolta(limit: int = None, existing_urls: set = None) -> List[Dict[str, Optional[str]]]:
    """
    Scrapes product data from Beervolta (Beer and Mead/Cider categories).
    Uses pagination to get all products.
    Includes anti-bot protection measures.
    Stops early if too many consecutive sold-out items are found.
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
                                
                                # In Smart Mode, we add NEW items to the list.
                                # But actually scrape.py logic says: "scrapers now return Smart: Page 1->N".
                                # And "In Smart Mode, we buffered Page 1 -> N (Newest -> Oldest)."
                                # So we just append everything we find, and let scrape.py handle duplicates/upserts?
                                # Wait, if it exists, we track consecutive_existing. Do we still yield it?
                                # The previous "Smart Reverse" logic buffered items and then processed them "in reverse order (oldest -> newest)" 
                                # and "only adding items that are not already in".
                                # If we return existing items too, scrape.py handles updates. 
                                # So yes, append all.
                                
                                all_products.append(p_item)
                                
                                if limit and len(all_products) >= limit:
                                    print(f"[Beervolta] Limit reached ({limit}). Stopping scan.")
                                    stop_scan = True
                                    break
                                
                                # Existing item check removed
                                # if consecutive_existing >= 10:
                                #     print(f"[Beervolta] Found 10 consecutive existing items. Stopping scan.")
                                #     stop_scan = True
                                #     break
                                    
                            except Exception as e:
                                print(f"[Beervolta] Error parsing item: {e}")
                                continue
                        
                        if not stop_scan:
                            scan_page += 1
                            # Scan limit removed
                            # if scan_page > 50: 
                            #    print("[Beervolta] Scan limit reached (50 pages). Stopping probe.")
                            #    break
                                
                    except Exception as e:
                        print(f"[Beervolta] Error scanning page {scan_page}: {e}")
                        break
                        
                continue # Move to next category (loop over categories)

            # Normal Mode (if existing_urls is None)
            # Limit removed: Loop until no products found
            # max_pages = 100 
            current_page = 1
            
            while True:
                # Loop condition
                # if current_page > max_pages: break

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
                    break
                
                # Get page content
                content = await page.content()
                soup = BeautifulSoup(content, 'lxml')
                
                # Check if there are products on this page
                items = soup.find_all('a', href=re.compile(r'\?pid='))
                
                if not items:
                    print(f"[Beervolta] No products found on page {current_page}. Stopping.")
                    break
                
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
                
                for p in page_products:
                    if p['stock_status'] == "Sold Out":
                        consecutive_sold_out += 1
                    else:
                        consecutive_sold_out = 0
                    
                    if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                         print(f"[Beervolta] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                         pass
                    
                    all_products.append(p)
                    if limit and len(all_products) >= limit: break
                
                if limit and len(all_products) >= limit: break
                
                if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Beervolta] Stopping pagination due to consecutive sold-out items.")
                    break
                
                print(f"[Beervolta] Extracted {len(page_products)} products from page {current_page}")

                if not page_products:
                    print(f"[Beervolta] No products extracted from page {current_page}. Stopping.")
                    break
                
                current_page += 1

        
        await context.close()
        await browser.close()

    print(f"\n[Beervolta] Total extracted: {len(all_products)} products from all categories.")
    return all_products

if __name__ == "__main__":
    # For testing purposes
    import json
    data = asyncio.run(scrape_beervolta(limit=5))
    print(json.dumps(data[:5], indent=2, ensure_ascii=False))
    print(f"\nTotal: {len(data)} products")

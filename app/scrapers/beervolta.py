import asyncio
import os
import re
import random
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# BeerVolta category base URLs (without page parameter)
CATEGORY_BASES = [
    "https://beervolta.com/?mode=cate&cbid=2270431&csid=0&sort=n",  # ビール
    "https://beervolta.com/?mode=cate&cbid=2830081&csid=0&sort=n"   # ミード・シードル
]

# Threshold for consecutive sold-out items before stopping
SOLD_OUT_THRESHOLD = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '10'))

async def scrape_beervolta(limit: int = None) -> List[Dict[str, Optional[str]]]:
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
        
        for category_base in CATEGORY_BASES:
            # Check if we've reached the limit
            if limit and len(all_products) >= limit:
                break
            
            print(f"\n[Beervolta] Processing category: {category_base}")
            
            # Start with page 1 to determine total pages
            page_num = 1
            max_pages = 100  # Safety limit
            
            while page_num <= max_pages:
                # Check limit
                if limit and len(all_products) >= limit:
                    break
                
                # Build URL with page parameter
                if page_num == 1:
                    url = category_base
                else:
                    url = f"{category_base}&page={page_num}"
                
                print(f"[Beervolta] Scraping page {page_num}: {url}")
                
                # Random delay before navigation
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    
                except Exception as e:
                    print(f"[Beervolta] Error navigating to page {page_num}: {e}")
                    break
                
                # Get page content
                content = await page.content()
                soup = BeautifulSoup(content, 'lxml')
                
                # Check if there are products on this page
                items = soup.find_all('a', href=re.compile(r'\?pid='))
                
                if not items:
                    print(f"[Beervolta] No products found on page {page_num}. Stopping.")
                    break
                
                print(f"[Beervolta] Found {len(items)} potential product links on page {page_num}")
                
                seen_urls = set()
                page_products = 0
                
                for item in items:
                    try:
                        # Check limit
                        if limit and len(all_products) >= limit:
                            break
                        
                        href = item.get('href', '')
                        if not href:
                            continue
                        
                        # Normalize URL
                        if href.startswith('/'):
                            link = f"https://beervolta.com{href}"
                        elif href.startswith('http'):
                            link = href
                        else:
                            link = f"https://beervolta.com/{href}"
                        
                        if link in seen_urls:
                            continue
                        seen_urls.add(link)

                        # Extract Image
                        img_tag = item.find('img')
                        img_url = img_tag.get('src') if img_tag else None
                        
                        # Extract Text Content
                        text_content = item.get_text(strip=True, separator='|')
                        parts = text_content.split('|')
                        
                        name = "Unknown"
                        price = "Unknown"
                        stock_status = "In Stock"
                        
                        # Simple heuristic for Price
                        for part in parts:
                            if '円' in part:
                                price = part
                                break
                        
                        # Simple heuristic for Name
                        potential_names = [p for p in parts if '円' not in p and len(p) > 2]
                        if potential_names:
                            name = potential_names[0]
                            
                        # Check Stock
                        upper_text = text_content.upper()
                        if '売切' in text_content or 'SOLD OUT' in upper_text:
                            stock_status = "Sold Out"
                            consecutive_sold_out += 1
                        elif '入荷予定' in text_content: 
                             stock_status = "Pre-order/Upcoming"
                             consecutive_sold_out = 0
                        else:
                            consecutive_sold_out = 0

                        if img_url: 
                            all_products.append({
                                "name": name,
                                "price": price,
                                "url": link,
                                "image": img_url,
                                "stock_status": stock_status,
                                "shop": "BEER VOLTA"
                            })
                            page_products += 1
                            
                            # Check if we've hit the consecutive sold-out threshold
                            if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                                print(f"[Beervolta] ⚠️  Early stop: {consecutive_sold_out} consecutive sold-out items detected.")
                                break

                    except Exception as e:
                        print(f"[Beervolta] Error parsing item: {e}")
                        continue
                
                print(f"[Beervolta] Extracted {page_products} products from page {page_num}")
                
                # Check if early stop was triggered
                if consecutive_sold_out >= SOLD_OUT_THRESHOLD:
                    print(f"[Beervolta] Stopping pagination due to consecutive sold-out items.")
                    break
                
                # If no products found on this page, we've reached the end
                if page_products == 0:
                    print(f"[Beervolta] No products extracted from page {page_num}. Stopping.")
                    break
                
                page_num += 1
        
        await context.close()
        await browser.close()

    print(f"\n[Beervolta] Total extracted: {len(all_products)} products from all categories.")
    return all_products

if __name__ == "__main__":
    # For testing purposes
    import json
    data = asyncio.run(scrape_beervolta())
    print(json.dumps(data[:5], indent=2, ensure_ascii=False))  # Show first 5
    print(f"\nTotal: {len(data)} products")

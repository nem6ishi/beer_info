import asyncio
import os
import logging
import re
import primp
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Optional, Set, Any, Dict
from dateutil import parser as date_parser
from ..core.types import ScrapedProduct

logger = logging.getLogger(__name__)

# Threshold for consecutive sold-out / existing items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
SHOP_NAME: str = "WITCH CRAFT MARKET"
BASE_URL: str = "https://witchcraftmarket.com"

def format_price(raw_price: Optional[str]) -> str:
    """Formats raw price string (e.g., '¥1,540' or '1540') into Japanese Yen string (e.g., '1540円')."""
    if not raw_price:
        return "Unknown"
    cleaned = re.sub(r'[^\d]', '', raw_price)
    if cleaned.isdigit():
        return f"{cleaned}円"
    return raw_price

def is_beer_product(title: str, brand: str) -> bool:
    """Check if the product is actually a beer product or relevant shop item."""
    title_lower = title.lower()

    if "グラス" in title_lower or "glass" in title_lower or "ステッカー" in title_lower or "tシャツ" in title_lower:
        if "コラボグラス" in title_lower and "ビール" not in title_lower and "セット" not in title_lower:
            return False

    return True

def fetch_html_with_primp(client: primp.Client, url: str, max_retries: int = 5) -> Optional[str]:
    """Fetch HTML content using primp with Chrome TLS impersonation and backoff."""
    for attempt in range(max_retries):
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429:
                wait_sec = (attempt + 1) * 5
                print(f"[{SHOP_NAME}] Rate limited (429) on {url}. Waiting {wait_sec}s...")
                import time
                time.sleep(wait_sec)
            else:
                print(f"[{SHOP_NAME}] HTTP {resp.status_code} fetching {url}")
                return resp.text if resp.status_code == 200 else None
        except Exception as e:
            print(f"[{SHOP_NAME}] Fetch exception for {url}: {e}")
            import time
            time.sleep(2)
    return None

def parse_craftbeer_page(html: str) -> List[ScrapedProduct]:
    """Parses product items directly from /collections/craftbeer HTML DOM."""
    soup = BeautifulSoup(html, 'html.parser')
    items: List[ScrapedProduct] = []

    product_nodes = soup.select('li.--collection-product-item')
    for node in product_nodes:
        # 1. Product Link & URL
        a_tag = node.find('a', href=True)
        if not a_tag:
            continue
        href = a_tag.get('href', '')
        if not href or '/products/' not in href:
            continue
        product_url = f"{BASE_URL}{href}" if href.startswith('/') else href

        # 2. Raw Title
        title_el = node.select_one('.--item-card-title')
        if not title_el:
            continue
        raw_title = title_el.get_text(strip=True)
        if not raw_title:
            continue

        # 3. Brand / Brewery Name (<div class="--item-card-brand-name">)
        brand_el = node.select_one('.--item-card-brand-name')
        brand_name = brand_el.get_text(strip=True) if brand_el else ""

        # Safe Brewery Formatting Rule:
        # If brand_name exists and is NOT shop name "WITCH CRAFT MARKET" -> prefix [brand_name]
        # If brand_name is missing or is "WITCH CRAFT MARKET" -> keep raw_title without bracket
        if brand_name and brand_name != SHOP_NAME and not brand_name.startswith("WCM"):
            if not raw_title.startswith('['):
                name = f"[{brand_name}] {raw_title}"
            else:
                name = raw_title
        else:
            name = raw_title

        # Check beer relevance
        if not is_beer_product(raw_title, brand_name):
            continue

        # 4. Price
        price_el = node.select_one('.price-item--regular, .price-item--sale, .--item-card-price-text, .price-item')
        raw_price = price_el.get_text(strip=True) if price_el else ""
        price = format_price(raw_price)

        # 5. Stock Status (SOLD OUT badge)
        all_item_text = ' '.join(node.stripped_strings).upper()
        if "SOLD OUT" in all_item_text or "売り切れ" in all_item_text or "在庫なし" in all_item_text:
            stock_status = "Sold Out"
        else:
            stock_status = "In Stock"

        # 6. Image URL
        img_tag = node.select_one('img.--item-card-img, img')
        image_url = None
        if img_tag:
            src = img_tag.get('src') or img_tag.get('data-src')
            if src:
                if src.startswith('//'):
                    image_url = f"https:{src}"
                elif src.startswith('/'):
                    image_url = f"{BASE_URL}{src}"
                else:
                    image_url = src

        product: ScrapedProduct = {
            "name": name,
            "price": price,
            "url": product_url,
            "image": image_url,
            "stock_status": stock_status,
            "shop": SHOP_NAME
        }

        items.append(product)

    return items

async def scrape_witch_craft_market(
    limit: Optional[int] = None,
    existing_urls: Optional[Set[str]] = None,
    full_scrape: bool = False
) -> List[ScrapedProduct]:
    """
    Scrapes product list directly from WITCH CRAFT MARKET /collections/craftbeer HTML pages.
    Directly extracts brand/brewery names from <div class="--item-card-brand-name"> for 100% precision.
    """
    all_products: List[ScrapedProduct] = []
    page: int = 1
    consecutive_existing: int = 0
    early_stop: bool = False

    print(f"[{SHOP_NAME}] Starting scrape directly from /collections/craftbeer HTML...")

    # Create Primp client with Chrome browser TLS impersonation
    client = primp.Client(impersonate="random", follow_redirects=True, timeout=30)
    loop = asyncio.get_event_loop()

    while True:
        if limit and len(all_products) >= limit:
            break

        url: str = f"{BASE_URL}/collections/craftbeer?page={page}"
        try:
            print(f"[{SHOP_NAME}] Fetching HTML page {page}...")
            html = await loop.run_in_executor(None, fetch_html_with_primp, client, url)
            if not html:
                print(f"[{SHOP_NAME}] Failed to fetch page {page}. Stopping.")
                break

            products = parse_craftbeer_page(html)
            if not products:
                print(f"[{SHOP_NAME}] No product items parsed on page {page}. Stopping.")
                break

            print(f"[{SHOP_NAME}] Page {page}: Parsed {len(products)} products from HTML.")

            for prod in products:
                if limit and len(all_products) >= limit:
                    break

                product_url = prod["url"]

                # Early stop check for existing URLs
                if existing_urls is not None and not full_scrape:
                    if product_url in existing_urls:
                        consecutive_existing += 1
                        if consecutive_existing >= SOLD_OUT_THRESHOLD:
                            print(f"[{SHOP_NAME}] ⚠️ Stopping: {consecutive_existing} consecutive existing items found.")
                            early_stop = True
                            break
                    else:
                        consecutive_existing = 0

                all_products.append(prod)

            if early_stop or (limit and len(all_products) >= limit):
                break

            page += 1
            await asyncio.sleep(0.3)  # Be polite

        except Exception as e:
            print(f"[{SHOP_NAME}] Exception on page {page}: {e}")
            break

    print(f"[{SHOP_NAME}] Finished! Scraped {len(all_products)} items.")
    return all_products

if __name__ == "__main__":
    import json
    items: List[ScrapedProduct] = asyncio.run(scrape_witch_craft_market(limit=15))
    print(json.dumps(items, indent=2, ensure_ascii=False))

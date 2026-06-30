import asyncio
import os
import httpx
from datetime import datetime, timezone
from typing import List, Optional, Set, Any, Dict
from dateutil import parser as date_parser
from ..core.types import ScrapedProduct

# Threshold for consecutive sold-out / existing items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
SHOP_NAME: str = "Antenna America"
BASE_URL: str = "https://www.antenna-america.com"

HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def format_price(raw_price: Optional[str]) -> str:
    """Formats raw price string (e.g., '1,200.00' or '1200') into Japanese Yen string (e.g., '1200円')."""
    if not raw_price:
        return "Unknown"
    cleaned: str = raw_price.split(".")[0].replace(",", "").strip()
    if cleaned.isdigit():
        return f"{cleaned}円"
    return raw_price

def is_beer_product(prod: Dict[str, Any]) -> bool:
    """Check if the Shopify product is actually a beer product (excluding cheese, sauces, merch, etc.)."""
    tags: List[str] = [str(t).lower() for t in prod.get("tags", [])]
    # Check for beer-related tags
    if any("beer" in t or "酒類" in t or "ビール" in t for t in tags):
        return True
    
    # Check product type as fallback
    prod_type: str = str(prod.get("product_type", "")).lower()
    if "food" in prod_type or "sauce" in prod_type or "cheese" in prod_type or "merch" in prod_type:
        return False
        
    return False

async def scrape_antenna_america(
    limit: Optional[int] = None,
    existing_urls: Optional[Set[str]] = None,
    full_scrape: bool = False
) -> List[ScrapedProduct]:
    """
    Scrapes product list from Antenna America using Shopify API (/products.json).
    Returns list of ScrapedProduct dictionaries.
    """
    all_products: List[ScrapedProduct] = []
    page: int = 1
    consecutive_existing: int = 0
    early_stop: bool = False

    print(f"[{SHOP_NAME}] Starting scrape (Shopify API)...")

    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        while True:
            if limit and len(all_products) >= limit:
                break

            api_url: str = f"{BASE_URL}/products.json?limit=250&page={page}"
            try:
                print(f"[{SHOP_NAME}] Fetching page {page}...")
                response = await client.get(api_url)
                if response.status_code != 200:
                    print(f"[{SHOP_NAME}] Page {page} returned status {response.status_code}. Stopping.")
                    break

                data: Dict[str, Any] = response.json()
                products: List[Dict[str, Any]] = data.get("products", [])
                if not products:
                    print(f"[{SHOP_NAME}] No more products found on page {page}. Stopping.")
                    break

                print(f"[{SHOP_NAME}] Page {page}: Fetched {len(products)} products.")

                for prod in products:
                    if limit and len(all_products) >= limit:
                        break

                    # Filter out non-beer items
                    if not is_beer_product(prod):
                        continue

                    title: str = prod.get('title', 'Unknown')
                    handle: str = prod.get('handle', '')
                    if not handle:
                        continue

                    product_url: str = f"{BASE_URL}/products/{handle}"

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

                    # Extract variants info
                    variants: List[Dict[str, Any]] = prod.get('variants', [])
                    in_stock: bool = any(v.get('available', False) for v in variants)
                    stock_status: str = "In Stock" if in_stock else "Sold Out"

                    raw_price: Optional[str] = None
                    if variants:
                        raw_price = str(variants[0].get('price', ''))
                    price: str = format_price(raw_price)

                    # Extract image
                    images: List[Dict[str, Any]] = prod.get('images', [])
                    image_url: Optional[str] = None
                    if images:
                        image_url = images[0].get('src')

                    p_item: ScrapedProduct = {
                        "name": title,
                        "price": price,
                        "url": product_url,
                        "image": image_url,
                        "stock_status": stock_status,
                        "shop": SHOP_NAME
                    }

                    raw_date = prod.get('published_at') or prod.get('created_at')
                    if raw_date:
                        try:
                            dt = date_parser.parse(raw_date)
                            dt_utc = dt.astimezone(timezone.utc)
                            p_item["first_seen"] = dt_utc.isoformat()
                        except Exception:
                            pass

                    all_products.append(p_item)

                if early_stop or (limit and len(all_products) >= limit):
                    break

                page += 1
                await asyncio.sleep(0.5)  # Be polite to the API

            except Exception as e:
                print(f"[{SHOP_NAME}] Exception on page {page}: {e}")
                break

    print(f"[{SHOP_NAME}] Finished! Scraped {len(all_products)} items.")
    return all_products

if __name__ == "__main__":
    import json
    items: List[ScrapedProduct] = asyncio.run(scrape_antenna_america(limit=5))
    print(json.dumps(items, indent=2, ensure_ascii=False))

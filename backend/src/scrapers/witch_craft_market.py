import asyncio
import os
import logging
import re
import json
import primp
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Set, Any, Dict, Tuple
from dateutil import parser as date_parser
from ..core.types import ScrapedProduct

logger = logging.getLogger(__name__)

# Threshold for consecutive sold-out / existing items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
SHOP_NAME: str = "WITCH CRAFT MARKET"
BASE_URL: str = "https://witchcraftmarket.com"

# Known title patterns for common breweries fallback
BREWERY_TITLE_PATTERNS: List[Tuple[str, str]] = [
    (r'^Stone\b', 'Stone Brewing'),
    (r'^せとうち', 'SETOUCHI'),
    (r'^Sierra Nevada\b', 'Sierra Nevada'),
    (r'^Karl Strauss\b', 'Karl Strauss'),
    (r'^Revision\b', 'Revision Brewing'),
    (r'^Rogue\b', 'Rogue Ales'),
    (r'^Pizza Port\b', 'Pizza Port'),
    (r'^Modern Times\b', 'Modern Times'),
    (r'^Mikkeller\b', 'Mikkeller'),
    (r'^Heretic\b', 'Heretic Brewing'),
    (r'^Belching Beaver\b', 'Belching Beaver'),
    (r'^KCBC\b', 'KCBC'),
    (r'^Knee Deep\b', 'Knee Deep Brewing'),
    (r'^Lost Coast\b', 'Lost Coast Brewery'),
    (r'^Offshoot\b', 'Offshoot Beer Co.'),
    (r'^Omnipollo\b', 'Omnipollo'),
    (r'^pFriem\b', 'pFriem Family Brewers'),
    (r'^RaR Brewing\b', 'RaR Brewing'),
    (r'^SingleCut\b', 'SingleCut Beersmiths'),
    (r'^Smog City\b', 'Smog City Brewing'),
    (r'^Societe\b', 'Societe Brewing'),
    (r'^Surly\b', 'Surly Brewing'),
    (r'^Topa Topa\b', 'Topa Topa Brewing'),
    (r'^West Coast Brewing\b', 'West Coast Brewing'),
    (r'^Y\.?\s*MARKET\b', 'Y. Market Brewing'),
    (r'^AMAKUSA\b', 'AMAKUSA SONAR BEER'),
    (r'WITCH OF OZU', 'WITCH OF OZU'),
]

def format_price(raw_price: Optional[str]) -> str:
    """Formats raw price string (e.g., '1030' or '1,030') into Japanese Yen string (e.g., '1030円')."""
    if not raw_price:
        return "Unknown"
    cleaned: str = raw_price.split(".")[0].replace(",", "").strip()
    if cleaned.isdigit():
        return f"{cleaned}円"
    return raw_price

def is_beer_product(prod: Dict[str, Any]) -> bool:
    """Check if the product is actually a beer product (excluding standalone glassware, merch, etc.)."""
    title: str = str(prod.get("title", "")).lower()
    prod_type: str = str(prod.get("product_type", "")).lower()

    if "グラス" in title or "glass" in title or "ステッカー" in title or "tシャツ" in title:
        if "グッズ" in prod_type or "merch" in prod_type or "アクセサリ" in prod_type:
            return False
        if "コラボグラス" in title and "ビール" not in title and "セット" not in title:
            return False

    return True

def load_static_brewery_map() -> Dict[str, str]:
    """Load pre-indexed brewery handle mapping from JSON file."""
    map_file: Path = Path(__file__).parent / "wcm_brewery_map.json"
    if map_file.exists():
        try:
            with open(map_file, encoding="utf-8") as f:
                data = json.load(f)
                print(f"[{SHOP_NAME}] Loaded {len(data)} static brewery mappings from wcm_brewery_map.json")
                return data
        except Exception as e:
            print(f"[{SHOP_NAME}] Warning: Could not load wcm_brewery_map.json: {e}")
    return {}

def fetch_with_primp(client: primp.Client, url: str, max_retries: int = 5) -> Optional[primp.Response]:
    """Fetch URL using primp with Chrome TLS impersonation and exponential backoff."""
    for attempt in range(max_retries):
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait_sec = (attempt + 1) * 3
                print(f"[{SHOP_NAME}] Rate limited (429) on {url}. Waiting {wait_sec}s...")
                import time
                time.sleep(wait_sec)
            else:
                print(f"[{SHOP_NAME}] HTTP {resp.status_code} fetching {url}")
                return resp
        except Exception as e:
            print(f"[{SHOP_NAME}] Fetch exception for {url}: {e}")
            import time
            time.sleep(1)
    return None

async def scrape_witch_craft_market(
    limit: Optional[int] = None,
    existing_urls: Optional[Set[str]] = None,
    full_scrape: bool = False
) -> List[ScrapedProduct]:
    """
    Scrapes product list from WITCH CRAFT MARKET using Shopify API (/collections/craftbeer/products.json)
    impersonating Chrome browser via primp.
    NEVER uses store name 'WITCH CRAFT MARKET' as brewery name.
    """
    all_products: List[ScrapedProduct] = []
    page: int = 1
    consecutive_existing: int = 0
    early_stop: bool = False

    print(f"[{SHOP_NAME}] Starting scrape (Primp / Shopify API)...")

    # Load static pre-indexed brewery map
    brewery_map: Dict[str, str] = load_static_brewery_map()

    # Create Primp client with Chrome browser TLS impersonation
    client = primp.Client(impersonate="random", follow_redirects=True, timeout=30)

    # Run blocking I/O calls in thread executor for async compatibility
    loop = asyncio.get_event_loop()

    while True:
        if limit and len(all_products) >= limit:
            break

        api_url: str = f"{BASE_URL}/collections/craftbeer/products.json?limit=250&page={page}"
        try:
            print(f"[{SHOP_NAME}] Fetching page {page}...")
            response = await loop.run_in_executor(None, fetch_with_primp, client, api_url)
            if not response or response.status_code != 200:
                status = response.status_code if response else 'No Response'
                print(f"[{SHOP_NAME}] Page {page} returned status {status}. Stopping.")
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

                raw_title: str = prod.get('title', 'Unknown').strip()
                handle: str = prod.get('handle', '')
                if not handle:
                    continue

                # Determine brewery name from collection mapping or title patterns
                brewery_name: Optional[str] = brewery_map.get(handle)
                if not brewery_name:
                    for pattern, bname_val in BREWERY_TITLE_PATTERNS:
                        if re.search(pattern, raw_title, re.IGNORECASE):
                            brewery_name = bname_val
                            break

                # NEVER fallback to "WITCH CRAFT MARKET" as brewery
                if brewery_name and brewery_name != SHOP_NAME and not raw_title.startswith('['):
                    title = f"[{brewery_name}] {raw_title}"
                else:
                    title = raw_title

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

                # Extract date information (updated_at > published_at > created_at)
                raw_date = prod.get('updated_at') or prod.get('published_at') or prod.get('created_at')
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
            await asyncio.sleep(0.3)  # Be polite to the API

        except Exception as e:
            print(f"[{SHOP_NAME}] Exception on page {page}: {e}")
            break

    print(f"[{SHOP_NAME}] Finished! Scraped {len(all_products)} items.")
    return all_products

if __name__ == "__main__":
    items: List[ScrapedProduct] = asyncio.run(scrape_witch_craft_market(limit=10))
    print(json.dumps(items, indent=2, ensure_ascii=False))

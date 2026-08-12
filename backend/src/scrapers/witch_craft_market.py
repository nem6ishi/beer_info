import asyncio
import os
import logging
import re
import httpx
from datetime import datetime, timezone
from typing import List, Optional, Set, Any, Dict, Tuple
from dateutil import parser as date_parser
from ..core.types import ScrapedProduct

logger = logging.getLogger(__name__)

# Threshold for consecutive sold-out / existing items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
SHOP_NAME: str = "WITCH CRAFT MARKET"
BASE_URL: str = "https://witchcraftmarket.com"

HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Non-brewery handles to filter out from collection-based brewery mapping
STYLE_HANDLES: Set[str] = {
    'craftbeer', 'ipa', 'hazy-ipa', 'lager', 'stout', 'sour', 'sour-ipa', 'pale-ale',
    'pilsner', 'porter', 'saison', 'ipl', 'kolsch', 'red-ipa', 'session-ipa', 'sour-ale',
    'smoothiesourale', 'mead', 'other', 'quick-order', 'juicy-fruits', 'hoppy-fruity',
    'mlb観戦', 'light', 'molty', 'sparkring-wine', 'orange-wine', 'red-wine', 'rose-wine',
    'ddhヘイジーダブルipa', 'style-other', 'cider', 'apple-cider', 'hard-cider', 'wine',
    'natural-wine', 'set', 'gift', 'glass', 'goods', 'sale', 'new-arrivals', 'recommend'
}

# Common brewery regex patterns for fallback when collection mapping is absent
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

async def fetch_with_retry(client: httpx.AsyncClient, url: str, max_retries: int = 4) -> Optional[httpx.Response]:
    """Fetch URL with exponential backoff on 429 rate limit."""
    for attempt in range(max_retries):
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait_sec = (attempt + 1) * 2
                print(f"[{SHOP_NAME}] Rate limited (429) on {url}. Waiting {wait_sec}s...")
                await asyncio.sleep(wait_sec)
            else:
                print(f"[{SHOP_NAME}] HTTP {resp.status_code} fetching {url}")
                return resp
        except Exception as e:
            print(f"[{SHOP_NAME}] Fetch exception for {url}: {e}")
            await asyncio.sleep(1)
    return None

async def fetch_brewery_mapping(client: httpx.AsyncClient) -> Dict[str, str]:
    """
    Fetches ALL Shopify collections across all pages and maps product handles to their official Brewery Collection Title.
    E.g. 'one-mind' -> 'AMAKUSA SONAR BEER'
    """
    mapping: Dict[str, str] = {}
    try:
        collections: List[Dict[str, Any]] = []
        page: int = 1

        # Fetch all collections pages
        while True:
            url = f"{BASE_URL}/collections.json?limit=250&page={page}"
            resp = await fetch_with_retry(client, url)
            if not resp or resp.status_code != 200:
                break
            data = resp.json().get("collections", [])
            if not data:
                break
            collections.extend(data)
            page += 1

        brewery_cols = [c for c in collections if c.get("handle") not in STYLE_HANDLES]
        sem = asyncio.Semaphore(3)  # Polite rate limit concurrency

        async def fetch_col(c: Dict[str, Any]) -> None:
            c_handle = c.get("handle")
            c_title = c.get("title")
            if not c_handle or not c_title:
                return

            async with sem:
                col_page: int = 1
                while True:
                    await asyncio.sleep(0.05)  # Polite pause
                    col_url = f"{BASE_URL}/collections/{c_handle}/products.json?limit=250&page={col_page}"
                    col_res = await fetch_with_retry(client, col_url, max_retries=2)
                    if not col_res or col_res.status_code != 200:
                        break
                    prods = col_res.json().get("products", [])
                    if not prods:
                        break
                    for p in prods:
                        phandle = p.get("handle")
                        if phandle and phandle not in mapping:
                            mapping[phandle] = c_title
                    col_page += 1

        # Concurrently fetch all brewery collection products
        await asyncio.gather(*[fetch_col(c) for c in brewery_cols])
        print(f"[{SHOP_NAME}] Successfully mapped {len(mapping)} products across {len(brewery_cols)} Brewery Collections.")
    except Exception as e:
        print(f"[{SHOP_NAME}] Warning: Failed to build brewery mapping: {e}")

    return mapping

async def scrape_witch_craft_market(
    limit: Optional[int] = None,
    existing_urls: Optional[Set[str]] = None,
    full_scrape: bool = False
) -> List[ScrapedProduct]:
    """
    Scrapes product list from WITCH CRAFT MARKET using Shopify API (/collections/craftbeer/products.json)
    with automatic Brewery Collection mapping and guaranteed [Brewery Name] prefix for 100% items.
    Returns list of ScrapedProduct dictionaries.
    """
    all_products: List[ScrapedProduct] = []
    page: int = 1
    consecutive_existing: int = 0
    early_stop: bool = False

    print(f"[{SHOP_NAME}] Starting scrape (Shopify API)...")

    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        # Build brewery mapping across all collection pages first
        brewery_map: Dict[str, str] = await fetch_brewery_mapping(client)

        while True:
            if limit and len(all_products) >= limit:
                break

            api_url: str = f"{BASE_URL}/collections/craftbeer/products.json?limit=250&page={page}"
            try:
                print(f"[{SHOP_NAME}] Fetching page {page}...")
                response = await fetch_with_retry(client, api_url)
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

                    if not brewery_name:
                        brewery_name = SHOP_NAME  # Fallback for original / unspecified beers

                    # Guaranteed [Brewery Name] title prefix for ALL items
                    if not raw_title.startswith('['):
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
                await asyncio.sleep(0.5)  # Be polite to the API

            except Exception as e:
                print(f"[{SHOP_NAME}] Exception on page {page}: {e}")
                break

    print(f"[{SHOP_NAME}] Finished! Scraped {len(all_products)} items.")
    return all_products

if __name__ == "__main__":
    import json
    items: List[ScrapedProduct] = asyncio.run(scrape_witch_craft_market(limit=10))
    print(json.dumps(items, indent=2, ensure_ascii=False))

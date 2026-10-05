import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from dateutil import parser as date_parser
import httpx
from ..core.types import ScrapedProduct

logger = logging.getLogger(__name__)

# Threshold for consecutive sold-out / existing items before stopping
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '50'))
SHOP_NAME: str = "マルホ酒店"
BASE_URL: str = "https://maruho.shop"

HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

def format_price(raw_price: Optional[str]) -> str:
    """Formats raw price string (e.g., '572.00' or '572') into Japanese Yen string (e.g., '572円')."""
    if not raw_price:
        return "Unknown"
    try:
        val: int = int(float(raw_price))
        return f"{val:,}円"
    except Exception:
        return f"{raw_price}円"

async def fetch_page_with_retry(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 4
) -> Optional[httpx.Response]:
    """Fetches a URL with exponential backoff on HTTP 429 or 5xx."""
    backoffs = [5, 15, 30, 60]
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(url)
            if response.status_code == 200:
                return response

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == max_retries:
                    logger.error(f"[{SHOP_NAME}] Max retries reached for {url}. Status: {response.status_code}")
                    return response

                # Check Retry-After header
                retry_after_str = response.headers.get("Retry-After")
                if retry_after_str and retry_after_str.isdigit():
                    wait_time = min(int(retry_after_str), 60)
                else:
                    wait_time = backoffs[min(attempt, len(backoffs) - 1)]

                logger.warning(f"[{SHOP_NAME}] Received status {response.status_code} for page. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(wait_time)
                continue

            logger.error(f"[{SHOP_NAME}] Unexpected status {response.status_code} for {url}")
            return response
        except (httpx.RequestError, httpx.TimeoutException) as e:
            if attempt == max_retries:
                logger.error(f"[{SHOP_NAME}] Network error on max retry for {url}: {e}")
                raise
            wait_time = backoffs[min(attempt, len(backoffs) - 1)]
            logger.warning(f"[{SHOP_NAME}] Request error: {e}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

    return None

async def scrape_maruho(
    limit: Optional[int] = None, 
    existing_urls: Optional[Set[str]] = None, 
    full_scrape: bool = False
) -> List[ScrapedProduct]:
    """
    Scrapes product data from Maruho Saketen using Shopify's /products.json API.
    """
    all_products: List[ScrapedProduct] = []
    consecutive_existing: int = 0
    page: int = 1
    page_limit: int = 250
    early_stop: bool = False

    logger.info(f"[{SHOP_NAME}] Starting scrape via Shopify API...")
    if existing_urls is not None and not full_scrape:
        logger.info(f"[{SHOP_NAME}] New Product Scrape mode enabled (threshold: {SOLD_OUT_THRESHOLD})")

    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        while True:
            if limit and len(all_products) >= limit:
                break

            url: str = f"{BASE_URL}/products.json?limit={page_limit}&page={page}"
            response = await fetch_page_with_retry(client, url)

            if not response or response.status_code != 200:
                msg = f"[{SHOP_NAME}] Failed to fetch page {page}: Status {response.status_code if response else 'None'}"
                logger.error(msg)
                if not all_products:
                    # If first page failed after retries, raise exception to trigger scraper health alert
                    raise RuntimeError(msg)
                break

            try:
                data: Dict[str, Any] = response.json()
            except Exception as e:
                logger.error(f"[{SHOP_NAME}] Failed to parse JSON on page {page}: {e}")
                if not all_products:
                    raise
                break

            products: List[Dict[str, Any]] = data.get('products', [])
            if not products:
                logger.info(f"[{SHOP_NAME}] No more products found on page {page}. Stopping.")
                break

            logger.info(f"[{SHOP_NAME}] Page {page}: Fetched {len(products)} products.")

            for prod in products:
                if limit and len(all_products) >= limit:
                    break

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
                            logger.info(f"[{SHOP_NAME}] ⚠️ Stopping: {consecutive_existing} consecutive existing items found.")
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

            if early_stop:
                break

            page += 1
            await asyncio.sleep(2.0)  # Rate limiting safeguard for Shopify

    logger.info(f"[{SHOP_NAME}] Finished! Scraped {len(all_products)} items.")
    return all_products

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    items: List[ScrapedProduct] = asyncio.run(scrape_maruho(limit=5))
    print(json.dumps(items, indent=2, ensure_ascii=False))

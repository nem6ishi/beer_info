import asyncio
import json
import logging
import os
import re
import ssl
from typing import Any, Dict, List, Optional, Set, cast
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup, Tag
from ..core.types import ScrapedProduct

logger = logging.getLogger(__name__)

# Early stop threshold for existing items
SOLD_OUT_THRESHOLD: int = int(os.getenv('SCRAPER_SOLD_OUT_THRESHOLD', '30'))

# Arome Search URL Template (EC-CUBE 4, sort by newest orderby=2, 80 items per page)
SEARCH_URL_TEMPLATE: str = "https://www.arome.jp/products/list?orderby=2&disp_number=80&pageno={page}"
BASE_URL: str = "https://www.arome.jp"

HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_legacy_ssl_context() -> ssl.SSLContext:
    """Creates an SSLContext that allows legacy ciphers (SECLEVEL=1) for servers with weak DH keys."""
    ctx = ssl.create_default_context()
    ctx.set_ciphers('DEFAULT@SECLEVEL=1')
    return ctx

def normalize_url(url: str) -> str:
    """Extracts product_id to ensure consistent URL matching with legacy DB records."""
    if not url:
        return url
    # EC-CUBE 4 URL format: /products/detail/1234
    match_new = re.search(r'/products/detail/(\d+)', url)
    if match_new:
        return f"{BASE_URL}/products/detail.php?product_id={match_new.group(1)}"
    # Legacy EC-CUBE 2 URL format: product_id=1234
    match_old = re.search(r'product_id=(\d+)', url)
    if match_old:
        return f"{BASE_URL}/products/detail.php?product_id={match_old.group(1)}"
    return url

def extract_product_data(item: Tag, is_area: bool = False) -> Optional[ScrapedProduct]:
    """
    Backward-compatibility parser for legacy markup or mock tests.
    """
    try:
        area: Optional[Tag] = item if is_area else item.select_one("div.gods_item")
        if not area:
            area = item

        link_tag = area.select_one('a')
        if not link_tag:
            return None

        relative_url = cast(str, link_tag.get("href", ""))
        product_url = urljoin(BASE_URL, relative_url)

        img_tag = link_tag.select_one("img") or area.select_one("img")
        image_url = urljoin(BASE_URL, cast(str, img_tag.get("src", ""))) if img_tag else None

        name_el = area.select_one(".product-name") or link_tag
        product_name = name_el.get_text(strip=True) if name_el else "Unknown"

        price_tag = area.select_one(".price, span[id^='price02_'], p.price, .product-price")
        price = "Unknown"
        if price_tag:
            m = re.search(r'([0-9,]+)', price_tag.get_text(strip=True))
            if m:
                clean_num = re.sub(r'[^0-9]', '', m.group(1))
                price = f"{clean_num}円"

        stock_status = "In Stock"
        area_text = area.get_text()
        if "sold out" in area_text.lower() or "売切" in area_text or "品切" in area_text:
            stock_status = "Sold Out"

        return {
            "name": product_name,
            "url": normalize_url(product_url),
            "price": price,
            "image": image_url,
            "stock_status": stock_status,
            "shop": "アローム"
        }
    except Exception as e:
        logger.error(f"[Arome] Error in extract_product_data: {e}")
        return None

def parse_list_page(html: str) -> List[ScrapedProduct]:
    """
    Parses an EC-CUBE 4 product list page.
    Uses DOM grid elements and embedded JS metadata for accurate price and stock info.
    """
    soup = BeautifulSoup(html, "html.parser")
    products: List[ScrapedProduct] = []

    # 1. Parse embedded productsClassCategories JavaScript variable for accurate stock and tax-included price
    categories_meta: Dict[str, Any] = {}
    m_cats = re.search(r'eccube\.productsClassCategories\s*=\s*(\{.*?\});\s*(?:var|\$|\n)', html, re.S)
    if m_cats:
        try:
            categories_meta = json.loads(m_cats.group(1))
        except Exception as e:
            logger.warning(f"[Arome] Failed to parse productsClassCategories JSON: {e}")

    # 2. Iterate over shelf items
    items = soup.select("li.ec-shelfGrid__item")
    for item in items:
        try:
            a_tag = item.select_one("a")
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            if not href:
                continue

            product_url = normalize_url(urljoin(BASE_URL, href))
            pid_match = re.search(r'product_id=(\d+)', product_url)
            pid = pid_match.group(1) if pid_match else ""

            # Image
            img_tag = item.select_one("p.ec-shelfGrid__item-image img") or item.select_one("img")
            image_url: Optional[str] = None
            img_alt: Optional[str] = None
            if img_tag:
                src = img_tag.get("src", "")
                if src:
                    image_url = urljoin(BASE_URL, src)
                img_alt = img_tag.get("alt")

            # Product name
            product_name = "Unknown"
            if img_alt and img_alt.strip():
                product_name = img_alt.strip()
            else:
                # Text paragraphs excluding price
                p_texts = [p.get_text(strip=True) for p in a_tag.select("p") if "price" not in p.get("class", [])]
                if p_texts:
                    product_name = p_texts[0]
                else:
                    product_name = a_tag.get_text(strip=True)

            # Price
            price = "Unknown"
            cat_data = categories_meta.get(pid)
            stock_found = False

            if cat_data and isinstance(cat_data, dict):
                # Traverse variations
                for _, v1 in cat_data.items():
                    if isinstance(v1, dict):
                        for _, v2 in v1.items():
                            if isinstance(v2, dict):
                                if v2.get("stock_find") is True:
                                    stock_found = True
                                p_tax = v2.get("price02_inc_tax") or v2.get("price02")
                                if p_tax and price == "Unknown":
                                    clean_p = re.sub(r'[^0-9]', '', str(p_tax))
                                    if clean_p and clean_p != '0':
                                        price = f"{clean_p}円"
            else:
                # Fallback stock detection from item DOM
                form_action = item.select_one("form[action*='/add_cart/']")
                item_text = item.get_text()
                if form_action and "品切" not in item_text and "sold out" not in item_text.lower():
                    stock_found = True

            # If price not found in metadata, check DOM
            if price == "Unknown":
                price_el = item.select_one(".price02-default, .ec-price__price, .price")
                if price_el:
                    m_p = re.search(r'([0-9,]+)', price_el.get_text())
                    if m_p:
                        clean_p = re.sub(r'[^0-9]', '', m_p.group(1))
                        if clean_p and clean_p != '0':
                            price = f"{clean_p}円"

            stock_status = "In Stock" if stock_found else "Sold Out"

            products.append({
                "name": product_name,
                "url": product_url,
                "price": price,
                "image": image_url,
                "stock_status": stock_status,
                "shop": "アローム"
            })
        except Exception as e:
            logger.error(f"[Arome] Error parsing shelf item: {e}")

    # Fallback to JSON-LD ItemList if shelf items weren't found
    if not products:
        m_ld = re.search(r'<script type="application/ld\+json">\s*(\{.*?"ItemList".*?\})\s*</script>', html, re.S)
        if m_ld:
            try:
                ld_data = json.loads(m_ld.group(1))
                for el in ld_data.get("itemListElement", []):
                    u = el.get("url")
                    n = el.get("name")
                    if u and n:
                        products.append({
                            "name": n,
                            "url": normalize_url(u),
                            "price": "Unknown",
                            "image": None,
                            "stock_status": "In Stock",
                            "shop": "アローム"
                        })
            except Exception as e:
                logger.warning(f"[Arome] Failed to parse JSON-LD ItemList: {e}")

    return products

async def fetch_product_detail(client: httpx.AsyncClient, product_url: str, sem: Optional[asyncio.Semaphore] = None) -> Optional[Dict[str, str]]:
    """
    Fetches the detail page to get the full product name, price, and image if needed.
    """
    try:
        if sem:
            await sem.acquire()
        try:
            response: httpx.Response = await client.get(product_url, timeout=30.0)
        finally:
            if sem:
                sem.release()
        if response.status_code != 200:
            return None

        response.encoding = response.encoding or 'utf-8'
        soup: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
        result: Dict[str, str] = {}

        # Product Title
        title_tag: Optional[Tag] = (
            soup.select_one("h2.ec-headingTitle") or
            soup.select_one("h2.productTitle") or
            soup.select_one("h2.title")
        )
        if title_tag:
            clean_title = title_tag.get_text(strip=True)
            clean_title = re.sub(r'¥[0-9,]+.*$', '', clean_title).strip()
            result["name"] = clean_title

        # Price
        price_tag: Optional[Tag] = (
            soup.select_one("span.ec-price__price") or
            soup.select_one("p.sale_price") or
            soup.select_one("#price02_default")
        )
        if price_tag:
            raw_price = price_tag.get_text(strip=True)
            # Prioritize tax-included price if indicated (e.g. 税込: ¥1,100)
            m_tax = re.search(r'税込[^0-9]*([0-9,]+)', raw_price)
            if m_tax:
                clean_num = re.sub(r'[^0-9]', '', m_tax.group(1))
                if clean_num and clean_num != '0':
                    result["price"] = f"{clean_num}円"
            else:
                m = re.search(r'([0-9,]+)', raw_price)
                if m:
                    clean_num = re.sub(r'[^0-9]', '', m.group(1))
                    if clean_num and clean_num != '0':
                        result["price"] = f"{clean_num}円"

        # Check JSON-LD for offers price if still missing
        if "price" not in result:
            for s in soup.select('script[type="application/ld+json"]'):
                if s.string and '"Product"' in s.string:
                    try:
                        p_data = json.loads(s.string)
                        if p_data.get("@type") == "Product":
                            offers = p_data.get("offers", {})
                            if isinstance(offers, dict) and offers.get("price"):
                                clean_num = re.sub(r'[^0-9]', '', str(offers["price"]))
                                if clean_num:
                                    result["price"] = f"{clean_num}円"
                                    break
                    except Exception:
                        pass

        return result if result else None
    except Exception as e:
        logger.error(f"[Arome] Error fetching detail for {product_url}: {e}")
        return None

async def fetch_full_name(client: httpx.AsyncClient, product_url: str, sem: Optional[asyncio.Semaphore] = None) -> Optional[str]:
    """
    Backward compatibility wrapper: fetches detail page and returns only the clean product name.
    """
    detail = await fetch_product_detail(client, product_url, sem)
    return detail.get("name") if detail else None

async def scrape_arome(limit: Optional[int] = None, existing_urls: Optional[Set[str]] = None, full_scrape: bool = False) -> List[ScrapedProduct]:
    """Scrapes product data from Arome."""
    products: List[ScrapedProduct] = []
    page: int = 1
    consecutive_existing: int = 0
    early_stop: bool = False

    logger.info(f"[Arome] Starting scrape (EC-CUBE 4)...")
    if existing_urls is not None:
        logger.info(f"[Arome] New product mode: Will stop after {SOLD_OUT_THRESHOLD} consecutive existing items")

    ssl_ctx = get_legacy_ssl_context()
    async with httpx.AsyncClient(verify=ssl_ctx, headers=HEADERS, timeout=30.0, follow_redirects=True) as client:
        while True:
            url: str = SEARCH_URL_TEMPLATE.format(page=page)
            logger.info(f"[Arome] Scraping page {page}: {url}")

            try:
                response: httpx.Response = await client.get(url)
                response.encoding = response.encoding or 'utf-8'

                if response.status_code != 200:
                    logger.warning(f"[Arome] Failed to fetch page {page}. Status: {response.status_code}")
                    break

                page_products = parse_list_page(response.text)
                if not page_products:
                    logger.info(f"[Arome] No items found on page {page}. Stopping.")
                    break

                logger.info(f"[Arome] Found {len(page_products)} items on page {page}.")

                # Identify items needing detail fetch (unknown prices or legacy mock data)
                tasks: List[ScrapedProduct] = []
                for p in page_products:
                    p_url = p["url"]
                    is_existing = existing_urls is not None and p_url in existing_urls
                    needs_detail = (p["price"] == "Unknown" or p["price"] == "0円")
                    if needs_detail and not is_existing:
                        tasks.append(p)

                if tasks:
                    logger.info(f"[Arome] Fetching details for {len(tasks)} items with concurrency control...")
                    sem: asyncio.Semaphore = asyncio.Semaphore(10)
                    detail_results = await asyncio.gather(
                        *[fetch_product_detail(client, p["url"], sem) for p in tasks],
                        return_exceptions=True
                    )
                    for p, res in zip(tasks, detail_results):
                        if isinstance(res, dict) and res:
                            if "name" in res and res["name"]:
                                p["name"] = res["name"]
                            if "price" in res and res["price"]:
                                p["price"] = res["price"]
                        elif isinstance(res, Exception):
                            logger.warning(f"[Arome] Detail fetch failed for {p['url']}: {res}")

                # Add to main list and evaluate early stop
                for p in page_products:
                    if limit and len(products) >= limit:
                        break

                    p_url = p["url"]
                    is_existing = existing_urls is not None and p_url in existing_urls
                    if existing_urls is not None:
                        if is_existing:
                            consecutive_existing += 1
                            if not full_scrape and consecutive_existing >= SOLD_OUT_THRESHOLD:
                                logger.info(f"[Arome] ⚠️ Stopping: {consecutive_existing} consecutive existing items found.")
                                early_stop = True
                                products.append(p)
                                break
                        else:
                            consecutive_existing = 0

                    products.append(p)

                if early_stop:
                    break

                if limit and len(products) >= limit:
                    logger.info(f"[Arome] Limit reached ({limit}). Stopping.")
                    break

                # If current page returned fewer than 80 items or reached max pages safeguard
                if len(page_products) < 80 or page >= 100:
                    logger.info(f"[Arome] Last page reached or page limit hit ({page}). Stopping.")
                    break

                page += 1
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"[Arome] Error scraping page {page}: {e}")
                break

    logger.info(f"[Arome] Finished! Scraped {len(products)} items.")
    return products

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    items: List[ScrapedProduct] = asyncio.run(scrape_arome(limit=5))
    print(json.dumps(items, indent=2, ensure_ascii=False))

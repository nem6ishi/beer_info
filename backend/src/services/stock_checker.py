import httpx
from bs4 import BeautifulSoup, Tag
import ssl
from typing import Optional, Dict, List, Tuple, TypedDict, Union

class StockCheckResult(TypedDict):
    """Result structure for stock and price checks."""
    stock_status: str
    price: Optional[str]

HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def fetch_url(client: httpx.AsyncClient, url: str) -> Tuple[Optional[str], int]:
    """Fetches a URL and returns content and status code."""
    try:
        # Create custom SSL context for legacy support (Arome)
        verify_ssl: Union[bool, ssl.SSLContext] = True
        try:
            ctx = ssl.create_default_context()
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
            verify_ssl = ctx
        except Exception:
            pass # Fallback to default verification if this fails
            
        if "arome.jp" in url:
            async with httpx.AsyncClient(verify=verify_ssl, timeout=15.0, follow_redirects=True) as local_client:
                response: httpx.Response = await local_client.get(url, headers=HEADERS)
        else:
            # Use shared client
            response = await client.get(url, headers=HEADERS, timeout=15.0)

        # Handle encoding
        content: Optional[str] = None
        encodings: List[str] = ['utf-8', 'euc-jp', 'shift_jis', 'cp932']
        
        for enc in encodings:
            try:
                content = response.content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        
        if not content:
            content = response.content.decode('utf-8', errors='replace')
            
        return content, response.status_code
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, 0

def check_stock_arome(soup: BeautifulSoup) -> str:
    """Checks stock status for Arome (ECCube)."""
    text: str = soup.get_text()
    if "品切" in text or "只今品切れ中" in text or "申し訳ございません" in text or "売り切れ" in text or "在庫切れ" in text:
        return "Sold Out"
        
    text_zone: Optional[Tag] = soup.select_one("div.text-zone")
    if text_zone and ("在庫切れ" in text_zone.get_text() or "品切" in text_zone.get_text()):
        return "Sold Out"
    
    if soup.select_one('img[alt="売り切れ"]') or soup.select_one('img[src*="soldout"]'):
        return "Sold Out"
        
    return "In Stock"

def check_stock_beervolta(soup: BeautifulSoup) -> str:
    """Checks stock status for BeerVolta."""
    text: str = soup.get_text()
    if "SOLD OUT" in text or "売切" in text or "完売" in text:
        return "Sold Out"
    
    if soup.select_one(".soldout") or soup.select_one("img[src*='soldout']"):
        return "Sold Out"
        
    cart_btn = soup.select_one("input[name='submit']") or soup.select_one("button.cart")
    if not cart_btn and ("SOLD OUT" in text.upper() or "売り切れ" in text):
        return "Sold Out"
    return "In Stock"

def check_stock_chouseiya(soup: BeautifulSoup) -> str:
    """Checks stock status for Chouseiya (MakeShop)."""
    text: str = soup.get_text()
    if "売り切れ" in text or "SOLD OUT" in text or "品切れ" in text or "完売" in text:
        return "Sold Out"
    
    # MakeShop specific checks
    if soup.select_one("img[src*='soldout']") or soup.select_one(".soldout"):
        return "Sold Out"
        
    cart_btn = soup.select_one("a[href*='cart']") or soup.select_one("input[value*='カート']")
    if not cart_btn:
        return "Sold Out"
        
    return "In Stock"

def check_stock_ichigo_ichie(soup: BeautifulSoup) -> str:
    """Checks stock status for Ichigo Ichie (MakeShop)."""
    if soup.select_one("button.btn-soldout") or soup.select_one(".btn-soldout"):
        return "Sold Out"
        
    if soup.select_one("button.btn-addcart") or soup.select_one("button.cart_in_async"):
        return "In Stock"
        
    text: str = soup.get_text()
    if "SOLD OUT" in text.upper() or "売り切れ" in text or "完売" in text:
        return "Sold Out"
        
    return "In Stock"

def extract_price_arome(soup: BeautifulSoup) -> Optional[str]:
    price_02 = soup.select_one("#price02_default")
    if price_02:
        val = price_02.get_text(strip=True).replace(",", "")
        if val and val.isdigit() and int(val) > 0:
            return f"{val}円"
            
    sale_el = soup.select_one(".sale_price")
    if sale_el:
        text = sale_el.get_text()
        m_tax = re.search(r'税込[^0-9]*([0-9,]+)', text)
        if m_tax:
            val = m_tax.group(1).replace(',', '')
            if val != '0':
                return f"{val}円"
                
    for p in soup.select(".price") + soup.select("#price"):
        text = p.get_text(strip=True)
        if text and text != "0円" and "0円" not in text:
            m = re.search(r'([1-9][0-9,]+)', text)
            if m:
                return f"{m.group(1).replace(',', '')}円"
    return None

def extract_price_beervolta(soup: BeautifulSoup) -> Optional[str]:
    price_el: Optional[Tag] = soup.select_one(".price") or soup.select_one(".product_price")
    if price_el:
        text = price_el.get_text(strip=True)
        m = re.search(r'([1-9][0-9,]+)', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"
        return text
    return None

def extract_price_chouseiya(soup: BeautifulSoup) -> Optional[str]:
    price_el: Optional[Tag] = soup.select_one(".price") or soup.select_one("#price")
    if price_el:
        text = price_el.get_text(strip=True)
        m = re.search(r'([1-9][0-9,]+)', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"
        return text
    return None

def extract_price_ichigo_ichie(soup: BeautifulSoup) -> Optional[str]:
    price_el: Optional[Tag] = soup.select_one(".product_price") or soup.select_one(".price") or soup.select_one(".product_data_price")
    if price_el:
        text = price_el.get_text(strip=True)
        m_tax = re.search(r'税込[^0-9]*([0-9,]+)', text)
        if m_tax:
            return f"{m_tax.group(1).replace(',', '')}円"
        nums = re.findall(r'([1-9][0-9,]{2,})', text)
        if nums:
            return f"{nums[-1].replace(',', '')}円"
        return text
    return None

async def check_stock_shopify(client: httpx.AsyncClient, url: str) -> StockCheckResult:
    """Checks stock and price for Shopify-based sites (Antenna America, Maruho Saketen) via .json endpoint."""
    result: StockCheckResult = {"stock_status": "Unknown", "price": None}
    json_url = f"{url.rstrip('/')}.json"
    try:
        response = await client.get(json_url, headers=HEADERS, timeout=15.0)
        if response.status_code == 404:
            result["stock_status"] = "Dead Link"
            return result
        if response.status_code != 200:
            result["stock_status"] = "Error"
            return result
        data = response.json()
        prod = data.get("product", {})
        variants = prod.get("variants", [])
        
        # If any variant explicitly has 'available' key, use it
        has_avail_key = any("available" in v for v in variants)
        if has_avail_key:
            in_stock = any(v.get("available", False) for v in variants)
            result["stock_status"] = "In Stock" if in_stock else "Sold Out"
        else:
            # Fallback to HTML DOM check if json doesn't expose availability
            content, status = await fetch_url(client, url)
            if status == 404:
                result["stock_status"] = "Dead Link"
                return result
            if content and status == 200:
                soup = BeautifulSoup(content, 'lxml')
                text = soup.get_text()
                if "SOLD OUT" in text.upper() or "売り切れ" in text or "完売" in text:
                    result["stock_status"] = "Sold Out"
                elif soup.select_one("button[name='add']") or soup.select_one("input[name='add']"):
                    result["stock_status"] = "In Stock"
                else:
                    result["stock_status"] = "Sold Out"
        if variants:
            raw_p = str(variants[0].get("price", ""))
            if raw_p:
                cleaned = raw_p.split(".")[0].replace(",", "").strip()
                if cleaned.isdigit():
                    result["price"] = f"{int(cleaned):,}円"
                else:
                    result["price"] = f"{raw_p}円"
    except Exception as e:
        print(f"Error checking Shopify JSON for {url}: {e}")
        result["stock_status"] = "Error"
    return result

async def check_stock_for_url(client: httpx.AsyncClient, url: str, shop: str) -> StockCheckResult:
    """
    Main entry point for checking stock and price of a product URL.
    """
    result: StockCheckResult = {"stock_status": "Unknown", "price": None}
    
    if not url: 
        return result
    
    # Shopify based shops directly use fast .json check
    if shop in ("Antenna America", "マルホ酒店"):
        return await check_stock_shopify(client, url)
    
    content, status = await fetch_url(client, url)
    
    # If the product page was removed (404 Not Found), treat it as Dead Link
    if status == 404:
        result["stock_status"] = "Dead Link"
        return result
        
    if not content or status != 200:
        result["stock_status"] = "Error"
        return result
        
    soup: BeautifulSoup = BeautifulSoup(content, 'lxml')
    
    if shop == "アローム":
        result["stock_status"] = check_stock_arome(soup)
        result["price"] = extract_price_arome(soup)
    elif shop == "BEER VOLTA":
        result["stock_status"] = check_stock_beervolta(soup)
        result["price"] = extract_price_beervolta(soup)
    elif shop == "ちょうせいや":
        result["stock_status"] = check_stock_chouseiya(soup)
        result["price"] = extract_price_chouseiya(soup)
    elif shop == "一期一会～る":
        result["stock_status"] = check_stock_ichigo_ichie(soup)
        result["price"] = extract_price_ichigo_ichie(soup)
    else:
        # Default fallback
        if "SOLD OUT" in soup.get_text().upper() or "売り切れ" in soup.get_text() or "完売" in soup.get_text():
            result["stock_status"] = "Sold Out"
        else:
            result["stock_status"] = "In Stock"
    
    return result

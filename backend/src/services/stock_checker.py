import httpx
from bs4 import BeautifulSoup, Tag
import re
import asyncio
import ssl
from typing import Optional, Dict, List, Tuple, TypedDict, Union, Any

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
    # Logic from scraper: check for specific text zone or button
    text_zone: Optional[Tag] = soup.select_one("div.text-zone")
    if text_zone and "在庫切れ" in text_zone.get_text():
        return "Sold Out"
    
    # Check images
    if soup.select_one('img[alt="売り切れ"]') or soup.select_one('img[src*="soldout"]'):
        return "Sold Out"
        
    # Check for Cart Button
    cart_btn: Optional[Tag] = soup.select_one("input[name='cart']") or soup.select_one("a.cart_btn")
    return "In Stock"

def check_stock_beervolta(soup: BeautifulSoup) -> str:
    """Checks stock status for BeerVolta."""
    # Logic: Look for "SOLD OUT" or "売切"
    text: str = soup.get_text()
    if "SOLD OUT" in text or "売切" in text:
        return "Sold Out"
    
    # Check for specific soldout overlay/class
    if soup.select_one(".soldout"):
        return "Sold Out"
        
    return "In Stock"

def check_stock_chouseiya(soup: BeautifulSoup) -> str:
    """Checks stock status for Chouseiya (MakeShop)."""
    # Logic: Look for "売り切れ" or "SOLD OUT"
    text: str = soup.get_text()
    if "売り切れ" in text or "SOLD OUT" in text:
        return "Sold Out"
        
    return "In Stock"

def check_stock_ichigo_ichie(soup: BeautifulSoup) -> str:
    """Checks stock status for Ichigo Ichie (MakeShop)."""
    # 1. Check for explicit Sold Out button
    if soup.select_one("button.btn-soldout") or soup.select_one(".btn-soldout"):
        return "Sold Out"
        
    # 2. Check for Add to Cart button -> In Stock
    if soup.select_one("button.btn-addcart") or soup.select_one("button.cart_in_async"):
        return "In Stock"
        
    return "In Stock"

def extract_price_arome(soup: BeautifulSoup) -> Optional[str]:
    """Extracts price for Arome."""
    price_el: Optional[Tag] = soup.select_one(".price") or soup.select_one("#price")
    if price_el:
        return price_el.get_text(strip=True)
    return None

def extract_price_beervolta(soup: BeautifulSoup) -> Optional[str]:
    """Extracts price for BeerVolta."""
    price_el: Optional[Tag] = soup.select_one(".price") or soup.select_one(".product_price")
    if price_el:
        return price_el.get_text(strip=True)
    return None

def extract_price_chouseiya(soup: BeautifulSoup) -> Optional[str]:
    """Extracts price for Chouseiya."""
    price_el: Optional[Tag] = soup.select_one(".price") or soup.select_one("#price")
    if price_el:
        return price_el.get_text(strip=True)
    return None

def extract_price_ichigo_ichie(soup: BeautifulSoup) -> Optional[str]:
    """Extracts price for Ichigo Ichie."""
    price_el: Optional[Tag] = soup.select_one(".product_price") or soup.select_one(".price")
    if price_el:
        return price_el.get_text(strip=True)
    price_area: Optional[Tag] = soup.select_one(".product_data_price")
    if price_area:
        return price_area.get_text(strip=True)
    return None

async def check_stock_for_url(client: httpx.AsyncClient, url: str, shop: str) -> StockCheckResult:
    """
    Main entry point for checking stock and price of a product URL.
    """
    result: StockCheckResult = {"stock_status": "Unknown", "price": None}
    
    if not url: 
        return result
    
    content, status = await fetch_url(client, url)
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
        if "SOLD OUT" in soup.get_text().upper() or "売り切れ" in soup.get_text():
            result["stock_status"] = "Sold Out"
        else:
            result["stock_status"] = "In Stock"
    
    return result

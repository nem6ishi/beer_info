import httpx
from bs4 import BeautifulSoup
import re
import asyncio

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def fetch_url(client, url):
    try:
        # Create custom SSL context for legacy support (Arome)
        import ssl
        verify_ssl = True
        try:
            ctx = ssl.create_default_context()
            ctx.set_ciphers('DEFAULT@SECLEVEL=1')
            verify_ssl = ctx
        except Exception:
            pass # Fallback to default verification if this fails
            
        # Use a new client for each request to apply specific SSL context??? 
        # The passed 'client' might not support changing verify context on the fly if it's already open.
        # But 'client' is passed from outside. 
        # If we need custom SSL, we might need to ignore the passed client and create a new one?
        # Or hopefully the caller can handle it?
        # Actually, `fetch_url` takes `client`. If `client` is reused, we can't change its SSL context easily.
        # However, creating a new client per request is expensive but necessary for Arome if the shared client is standard.
        # Let's create a local client JUST for this request if Arome?
        # Or better: The caller (`check_stock_for_url`) passes the client.
        # I should probably modify `check_stock_for_url` to handle the client creation or context.
        # BUT current architecture passes one client for concurrency.
        # HACK: If url is Arome, create a temporary client with custom SSL.
        
        if "arome.jp" in url:
            async with httpx.AsyncClient(verify=verify_ssl, timeout=15.0, follow_redirects=True) as local_client:
                response = await local_client.get(url, headers=HEADERS)
        else:
            # Use shared client
            response = await client.get(url, headers=HEADERS, timeout=15.0)

        # Handle encoding
        content = None
        encodings = ['utf-8', 'euc-jp', 'shift_jis', 'cp932']
        
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

def check_stock_arome(soup):
    # Logic from scraper: check for specific text zone or button
    text_zone = soup.select_one("div.text-zone")
    if text_zone and "在庫切れ" in text_zone.get_text():
        return "Sold Out"
    
    # Check images
    if soup.select_one('img[alt="売り切れ"]') or soup.select_one('img[src*="soldout"]'):
        return "Sold Out"
        
    # Check for Cart Button (input type="image" name="image" often in Arome/ECCube?)
    # Arome usually has a form with class "cart_btn" or similar if in stock
    cart_btn = soup.select_one("input[name='cart']") or soup.select_one("a.cart_btn")
    # If explicit sold out not found, assume in stock, but maybe verify cart button?
    # Listing scraper logic is "In Stock" default unless "Sold Out" found. let's stick to that.
    return "In Stock"

def check_stock_beervolta(soup):
    # Logic: Look for "SOLD OUT" or "売切"
    text = soup.get_text()
    if "SOLD OUT" in text or "売切" in text:
        return "Sold Out"
    
    # Check for specific soldout overlay/class
    if soup.select_one(".soldout"):
        return "Sold Out"
        
    # Check for cart button presence to be sure?
    # Hidden input names commonly found in Makeshop/ColorMe
    if soup.find("input", {"name": "is_async_cart_in"}):
        return "In Stock"
        
    return "In Stock"

def check_stock_chouseiya(soup):
    # Logic: Look for "売り切れ" or "SOLD OUT"
    text = soup.get_text()
    # Chouseiya detail page usually has "売り切れ" near price or cart if sold out
    if "売り切れ" in text or "SOLD OUT" in text:
        # Be careful not to match "Selling out fast!" text if it existed, but usually Japanese sites are clear
        # Check specific containers if possible
        return "Sold Out"
        
    # Cart button presence
    cart_btn = soup.select_one("input[value='カートに入れる']") or soup.select_one("img[alt='カートにれる']") # Typo safe?
    # MakeShop usually "input type=submit value=カートに入れる" is standard
    # If no cart button and no sold out text? 
    return "In Stock"

def check_stock_ichigo_ichie(soup):
    # Ichigo Ichie (151l.shop - MakeShop based)
    # Key indicators found via browser inspection:
    # - Sold Out: button.btn-soldout (disabled, text "SOLD OUT")
    # - In Stock: button.btn-addcart.cart_in_async (text "カートに入れる")
    
    # 1. Check for explicit Sold Out button
    if soup.select_one("button.btn-soldout") or soup.select_one(".btn-soldout"):
        return "Sold Out"
        
    # 2. Check for Add to Cart button -> In Stock
    if soup.select_one("button.btn-addcart") or soup.select_one("button.cart_in_async"):
        return "In Stock"
        
    # 3. Fallback: If neither found, default to In Stock (avoid false Sold Out)
    return "In Stock"

def extract_price_arome(soup) -> str | None:
    # Arome: Price is usually in .price or span containing ¥
    price_el = soup.select_one(".price") or soup.select_one("#price")
    if price_el:
        return price_el.get_text(strip=True)
    # Fallback: look for text with ¥ in product area
    return None

def extract_price_beervolta(soup) -> str | None:
    # BeerVolta: .price or .product_price
    price_el = soup.select_one(".price") or soup.select_one(".product_price")
    if price_el:
        return price_el.get_text(strip=True)
    return None

def extract_price_chouseiya(soup) -> str | None:
    # Chouseiya (MakeShop): .price or span in the detail area
    price_el = soup.select_one(".price") or soup.select_one("#price")
    if price_el:
        return price_el.get_text(strip=True)
    return None

def extract_price_ichigo_ichie(soup) -> str | None:
    # 151l.shop: .product_price or span with yen
    price_el = soup.select_one(".product_price") or soup.select_one(".price")
    if price_el:
        return price_el.get_text(strip=True)
    # Alternative: Look for span with 税込
    price_area = soup.select_one(".product_data_price")
    if price_area:
        return price_area.get_text(strip=True)
    return None

async def check_stock_for_url(client: httpx.AsyncClient, url: str, shop: str) -> dict:
    """
    Returns dict with:
      - stock_status: "In Stock", "Sold Out", or "Error"
      - price: extracted price string or None
    """
    result = {"stock_status": "Unknown", "price": None}
    
    if not url: 
        return result
    
    content, status = await fetch_url(client, url)
    if not content or status != 200:
        result["stock_status"] = "Error"
        return result
        
    soup = BeautifulSoup(content, 'lxml')
    
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

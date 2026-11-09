import re
import json
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
    """Checks stock status for Arome (ECCube 4 and legacy)."""
    # 1. Check schema.org Product JSON-LD offers.availability
    for s in soup.select('script[type="application/ld+json"]'):
        if s.string and '"Product"' in s.string:
            try:
                data = json.loads(s.string)
                if data.get("@type") == "Product":
                    offers = data.get("offers")
                    if isinstance(offers, dict):
                        avail = offers.get("availability", "")
                        if "OutOfStock" in avail:
                            return "Sold Out"
                        elif "InStock" in avail:
                            return "In Stock"
            except Exception:
                pass

    # 2. Check embedded productsClassCategories JS
    soup_text = soup.get_text()
    m_cats = re.search(r'eccube\.productsClassCategories\s*=\s*(\{.*?\});\s*(?:var|\$|\n)', str(soup), re.S)
    if m_cats:
        try:
            cats = json.loads(m_cats.group(1))
            has_stock = False
            for _, v1 in cats.items():
                if isinstance(v1, dict):
                    for _, v2 in v1.items():
                        if isinstance(v2, dict) and v2.get("stock_find") is True:
                            has_stock = True
                            break
            return "In Stock" if has_stock else "Sold Out"
        except Exception:
            pass

    # 3. Check EC-CUBE 4 action buttons
    cart_btn = soup.select_one(".ec-blockBtn--action, .add-cart, button[type='submit']")
    if cart_btn:
        btn_text = cart_btn.get_text(strip=True)
        if "品切" in btn_text or "売り切れ" in btn_text or "sold out" in btn_text.lower():
            return "Sold Out"

    # 4. Legacy checks
    text_zone: Optional[Tag] = soup.select_one("div.text-zone, .ec-productRole__profile")
    if text_zone and ("在庫切れ" in text_zone.get_text() or "品切" in text_zone.get_text() or "申し訳ございません" in text_zone.get_text()):
        return "Sold Out"

    if soup.select_one('img[alt="売り切れ"]') or soup.select_one('img[src*="soldout"]'):
        return "Sold Out"

    return "In Stock"

def check_stock_beervolta(soup: BeautifulSoup) -> str:
    """Checks stock status for BeerVolta."""
    # 1. Check primary product cart button
    cart_btn = soup.select_one("button.c-product-button") or soup.select_one("form[action*='/cart/proxy/basket/items/add'] button")
    if cart_btn:
        classes = cart_btn.get("class", [])
        if isinstance(classes, list):
            class_str = " ".join(classes)
        else:
            class_str = str(classes)
        btn_text = cart_btn.get_text(strip=True).upper()
        if "ISDISABLED" in class_str.upper() or cart_btn.has_attr("disabled") or "SOLD OUT" in btn_text or "売り切れ" in btn_text:
            return "Sold Out"
        return "In Stock"

    # 2. Check for explicit soldout badges/elements
    if soup.select_one(".soldout, .c-product-soldout, [class*='soldout']") or soup.select_one("img[src*='soldout']"):
        return "Sold Out"

    # 3. Check within product information section
    info_section = soup.select_one(".l-product-information") or soup.select_one(".c-product-detail")
    if info_section:
        info_text = info_section.get_text().upper()
        if "SOLD OUT" in info_text or "売り切れ" in info_text or "完売" in info_text:
            return "Sold Out"

    # 4. Fallback button checks
    legacy_cart_btn = soup.select_one("input[name='submit']") or soup.select_one("button.cart")
    if legacy_cart_btn:
        return "In Stock"

    return "Sold Out"

def check_stock_chouseiya(soup: BeautifulSoup) -> str:
    """Checks stock status for Chouseiya (MakeShop)."""
    # 1. Look for MakeShop order form (form1)
    form = soup.find("form", attrs={"name": "form1"}) or soup.select_one("#detail_cart")
    if form:
        form_text = form.get_text()

        # Check for explicit soldout/out-of-stock text inside form or quantity area
        qty_el = form.select_one(".quantity, p.quantity")
        qty_text = qty_el.get_text() if qty_el else ""
        if "品切れ" in qty_text or "売り切れ" in qty_text or "0個" in qty_text:
            return "Sold Out"

        # Check for basket action link inside order form
        has_basket_btn = False
        for a in form.find_all("a"):
            href = a.get("href", "")
            if "send(" in href or "JavaScript:send" in href or "basket.html" in href:
                has_basket_btn = True
                break
        if not has_basket_btn:
            img = form.find("img", alt=re.compile(r"かごに入れる|カートに入れる"))
            if img and img.find_parent("a"):
                has_basket_btn = True
            else:
                btn_img = form.find("img", src=re.compile(r"r_basketBtn|basketBtn"))
                if btn_img and btn_img.find_parent("a"):
                    has_basket_btn = True

        if has_basket_btn:
            return "In Stock"

        if "品切れ" in form_text or "売り切れ" in form_text or "SOLD OUT" in form_text.upper() or "完売" in form_text:
            return "Sold Out"
        return "Sold Out"

    # 2. Fallback check for basket button anywhere
    basket_link = soup.find("a", href=re.compile(r"send\(")) or soup.find("img", alt=re.compile(r"かごに入れる"))
    if basket_link:
        return "In Stock"

    if soup.select_one("img[src*='soldout']") or soup.select_one(".soldout"):
        return "Sold Out"

    return "Sold Out"

def check_stock_witch_craft_market(soup: BeautifulSoup) -> str:
    """Checks stock status for WITCH CRAFT MARKET (Shopify-based custom theme)."""
    # 1. Product add to cart button
    cart_btn = soup.select_one("button.--detail-checkout-button") or soup.select_one("form[action*='/cart/add'] button[name='add']") or soup.select_one("button[name='add']")
    if cart_btn:
        classes = cart_btn.get("class", [])
        class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
        btn_text = cart_btn.get_text(strip=True).upper()
        if "--sold-out" in class_str or "tw-hidden" in class_str or cart_btn.has_attr("disabled") or "SOLD OUT" in btn_text or "売り切れ" in btn_text:
            return "Sold Out"
        return "In Stock"

    # 2. Detail section checks
    detail_container = soup.select_one(".--detail-checkout-container") or soup.select_one(".product__info-container")
    if detail_container:
        container_text = detail_container.get_text().upper()
        if "SOLD OUT" in container_text or "売り切れ" in container_text:
            return "Sold Out"

    # 3. Collection / general sold out indicators
    if soup.select_one(".--detail-checkout-button.--sold-out") or soup.select_one(".price--sold-out"):
        return "Sold Out"

    return "Sold Out"

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
    # 1. EC-CUBE 4 price element (e.g. ￥2,310)
    price_eccube4 = soup.select_one("span.ec-price__price, .ec-price__price, .price02-default")
    if price_eccube4:
        val = re.sub(r'[^0-9]', '', price_eccube4.get_text())
        if val and val != '0':
            return f"{val}円"

    # 2. Check schema.org Product JSON-LD offers.price
    for s in soup.select('script[type="application/ld+json"]'):
        if s.string and '"Product"' in s.string:
            try:
                data = json.loads(s.string)
                if data.get("@type") == "Product":
                    offers = data.get("offers")
                    if isinstance(offers, dict) and offers.get("price"):
                        val = re.sub(r'[^0-9]', '', str(offers["price"]))
                        if val and val != '0':
                            return f"{val}円"
            except Exception:
                pass

    # 3. Legacy selectors
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
    # 1. New theme price selector (.c-product-priceMain, .c-product-price)
    price_main = soup.select_one(".c-product-priceMain, .c-product-price")
    if price_main:
        text = price_main.get_text(strip=True)
        # Prefer tax-included price if present (e.g. 1,270円(税込1,397円))
        tax_m = re.search(r'税込\s*([0-9,]+)円?', text)
        if tax_m:
            return f"{tax_m.group(1).replace(',', '')}円"
        m = re.search(r'([1-9][0-9,]+)', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"

    # 2. Legacy selectors
    price_el: Optional[Tag] = soup.select_one(".price") or soup.select_one(".product_price")
    if price_el:
        text = price_el.get_text(strip=True)
        m = re.search(r'([1-9][0-9,]+)', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"
        return text
    return None

def extract_price_chouseiya(soup: BeautifulSoup) -> Optional[str]:
    # 1. Look for MakeShop price row / table (M_usualValue, M_infoTable)
    usual_row = soup.select_one(".M_usualValue") or soup.select_one(".M_infoTable")
    if usual_row:
        text = usual_row.get_text(strip=True)
        m = re.search(r'([1-9][0-9,]*)\s*円', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"

    # 2. Form price or general price
    price_el: Optional[Tag] = (
        soup.select_one("form[name='form1'] .price")
        or soup.select_one(".price")
        or soup.select_one("#price")
        or soup.select_one("span.price")
    )
    if price_el:
        text = price_el.get_text(strip=True)
        m = re.search(r'([1-9][0-9,]*)\s*円', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"

    # 3. Form text search for 価格 :1,280円
    form = soup.find("form", attrs={"name": "form1"})
    if form:
        form_text = form.get_text()
        m = re.search(r'価格\s*[:：]?\s*([1-9][0-9,]*)\s*円', form_text)
        if m:
            return f"{m.group(1).replace(',', '')}円"

    return None

def extract_price_witch_craft_market(soup: BeautifulSoup) -> Optional[str]:
    price_el = (
        soup.select_one("span.--detail-price-regular-text")
        or soup.select_one("div.--detail-price-regular")
        or soup.select_one(".--item-card-price-text")
        or soup.select_one(".price-item--regular")
        or soup.select_one(".price-item--sale")
    )
    if price_el:
        text = price_el.get_text(strip=True)
        m = re.search(r'([1-9][0-9,]+)', text)
        if m:
            return f"{m.group(1).replace(',', '')}円"
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
    elif shop == "WITCH CRAFT MARKET":
        result["stock_status"] = check_stock_witch_craft_market(soup)
        result["price"] = extract_price_witch_craft_market(soup)
    else:
        # Default fallback
        if "SOLD OUT" in soup.get_text().upper() or "売り切れ" in soup.get_text() or "完売" in soup.get_text():
            result["stock_status"] = "Sold Out"
        else:
            result["stock_status"] = "In Stock"
    
    return result

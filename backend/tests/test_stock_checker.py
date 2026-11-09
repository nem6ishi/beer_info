import pytest
from bs4 import BeautifulSoup
from src.services.stock_checker import (
    check_stock_chouseiya,
    extract_price_chouseiya,
    check_stock_beervolta,
    extract_price_beervolta,
    check_stock_witch_craft_market,
    extract_price_witch_craft_market,
)

# 1. ちょうせいや (Chouseiya) Tests
def test_chouseiya_in_stock():
    html = """
    <html>
      <form name="form1" action="/shop/basket.html">
        <a href="JavaScript:send('','');"><img alt="かごに入れる" src="https://example.com/r_basketBtn.png"/></a>
        <tr class="M_usualValue"><td>価格 :720円（税込）</td></tr>
      </form>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert check_stock_chouseiya(soup) == "In Stock"
    assert extract_price_chouseiya(soup) == "720円"

def test_chouseiya_sold_out():
    html = """
    <html>
      <form name="form1" action="/shop/basket.html">
        <p class="quantity">数量 品切れ</p>
        <div class="detailInfo">価格 :1,280円（税込）</div>
      </form>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert check_stock_chouseiya(soup) == "Sold Out"
    assert extract_price_chouseiya(soup) == "1280円"


# 2. BEER VOLTA Tests
def test_beervolta_in_stock():
    html = """
    <html>
      <section class="l-product-information">
        <div class="c-product-price">
          <span class="c-product-priceMain">1,270円(税込1,397円)</span>
        </div>
        <button class="c-product-button" type="submit">カートに入れる / Add to Cart</button>
      </section>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert check_stock_beervolta(soup) == "In Stock"
    assert extract_price_beervolta(soup) == "1397円"

def test_beervolta_sold_out():
    html = """
    <html>
      <section class="l-product-information">
        <div class="c-product-price">
          <span class="c-product-priceMain">5,927円(税込6,520円)</span>
        </div>
        <button class="c-product-button isDisabled" disabled="">SOLD OUT</button>
      </section>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert check_stock_beervolta(soup) == "Sold Out"
    assert extract_price_beervolta(soup) == "6520円"


# 3. WITCH CRAFT MARKET Tests
def test_wcm_in_stock():
    html = """
    <html>
      <div class="--detail-price-container">
        <span class="--detail-price-regular-text">¥1,560</span>
      </div>
      <button type="submit" name="add" class="--detail-checkout-button --primary">カートに入れる</button>
      <div class="related-products">SOLD OUT OTHER BEER</div>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert check_stock_witch_craft_market(soup) == "In Stock"
    assert extract_price_witch_craft_market(soup) == "1560円"

def test_wcm_sold_out():
    html = """
    <html>
      <div class="--detail-price-container">
        <span class="--detail-price-regular-text">¥1,270</span>
      </div>
      <button name="add" class="--detail-checkout-button --sold-out" disabled>🙏SOLD OUT</button>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    assert check_stock_witch_craft_market(soup) == "Sold Out"
    assert extract_price_witch_craft_market(soup) == "1270円"

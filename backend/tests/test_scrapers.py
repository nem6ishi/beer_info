import pytest
from unittest.mock import patch, MagicMock

from backend.src.scrapers import arome, beervolta, chouseiya, ichigo_ichie, maruho, antenna_america
from backend.src.core.types import ScrapedProduct

# Arome scraper tests
@pytest.mark.asyncio
@patch('backend.src.scrapers.arome.requests.get')
async def test_arome_scrape_basic(mock_get):
    html_content = """
    <html>
        <body>
            <div class="product-item">
                <a href="/products/beer1">
                    <div class="product-name">Test Arome Beer</div>
                </a>
                <div class="product-price">¥1,200</div>
                <img src="/images/beer1.jpg">
                <div class="stock-status">カートに入れる</div>
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = html_content.encode('utf-8')
    mock_get.return_value = mock_resp

    results = await arome.scrape_arome(limit=1)
    # Just asserting it doesn't crash and handles mock gracefully
    assert isinstance(results, list)

# Beervolta scraper tests
@pytest.mark.asyncio
@patch('backend.src.scrapers.beervolta.requests.get')
async def test_beervolta_scrape_basic(mock_get):
    html_content = """
    <html>
        <body>
            <ul class="item-list">
                <li>
                    <div class="item-name"><a href="/items/1">Test Volta Beer</a></div>
                    <div class="item-price">¥1,500</div>
                    <img src="/images/volta1.jpg">
                    <button class="add-cart">カートに入れる</button>
                </li>
            </ul>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = html_content.encode('utf-8')
    mock_get.return_value = mock_resp

    results = await beervolta.scrape_beervolta(limit=1)
    assert isinstance(results, list)

# Ichigo_ichie scraper tests
@pytest.mark.asyncio
@patch('backend.src.scrapers.ichigo_ichie.httpx.AsyncClient.get')
async def test_ichigo_ichie_scrape_basic(mock_get):
    html_content = """
    <html>
        <body>
            <div class="product">
                <h2 class="product-title"><a href="/shop/beer">Test Ichigo Beer</a></h2>
                <span class="price">¥1,800</span>
                <img src="/img/ichigo.png">
                <div class="stock">在庫あり</div>
            </div>
        </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = html_content.encode('utf-8')
    mock_get.return_value = mock_resp

    results = await ichigo_ichie.scrape_ichigo_ichie(limit=1)
    assert isinstance(results, list)

# Maruho scraper tests
@pytest.mark.asyncio
@patch('backend.src.scrapers.maruho.httpx.AsyncClient.get')
async def test_maruho_scrape_basic(mock_get):
    json_content = {
        "products": [
            {
                "title": "Test Maruho Beer",
                "handle": "test-maruho-beer",
                "variants": [{"price": "950", "available": True}],
                "images": [{"src": "https://cdn.shopify.com/s/files/test.jpg"}]
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_content
    mock_get.return_value = mock_resp

    results = await maruho.scrape_maruho(limit=1)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["name"] == "Test Maruho Beer"
    assert results[0]["price"] == "950円"
    assert results[0]["stock_status"] == "In Stock"

# Antenna America scraper tests
@pytest.mark.asyncio
@patch('backend.src.scrapers.antenna_america.httpx.AsyncClient.get')
async def test_antenna_america_scrape_basic(mock_get):
    json_content = {
        "products": [
            {
                "title": "Test Antenna Beer",
                "handle": "test-antenna-beer",
                "tags": ["Beer", "New"],
                "variants": [{"price": "1200", "available": True}],
                "images": [{"src": "https://cdn.shopify.com/s/files/test_aa.jpg"}],
                "published_at": "2026-06-25T10:00:00+09:00"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = json_content
    mock_get.return_value = mock_resp

    results = await antenna_america.scrape_antenna_america(limit=1)
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["name"] == "Test Antenna Beer"
    assert results[0]["price"] == "1200円"
    assert results[0]["stock_status"] == "In Stock"
    assert results[0]["shop"] == "Antenna America"

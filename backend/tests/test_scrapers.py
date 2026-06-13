import pytest
from unittest.mock import patch, MagicMock

from backend.src.scrapers import arome, beervolta, chouseiya, ichigo_ichie
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

    results = await arome.scrape(limit=1)
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

    results = await beervolta.scrape(limit=1)
    assert isinstance(results, list)

# Ichigo_ichie scraper tests
@pytest.mark.asyncio
@patch('backend.src.scrapers.ichigo_ichie.requests.get')
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

    results = await ichigo_ichie.scrape(limit=1)
    assert isinstance(results, list)

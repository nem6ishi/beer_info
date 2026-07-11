#!/usr/bin/env python
"""アロームの詳細ページから完全な商品名を取得するテスト"""
import sys
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scrapers.arome import fetch_full_name, fetch_product_detail, get_legacy_ssl_context
import httpx

@pytest.mark.asyncio
@patch('src.scrapers.arome.httpx.AsyncClient.get')
async def test_arome_detail_fetch(mock_get):
    url = "https://www.arome.jp/products/detail.php?product_id=5725"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '<html><body><h2 class="productTitle">Full Arome Beer Name ¥1,000 (税込: ¥ 1,100)</h2><p class="sale_price">販売価格: ¥1,000(税込: ¥1,100)</p></body></html>'
    mock_get.return_value = mock_resp

    async with httpx.AsyncClient() as client:
        detail = await fetch_product_detail(client, url)
        assert detail is not None
        assert detail["name"] == "Full Arome Beer Name"
        assert detail["price"] == "1100円"

        full_name = await fetch_full_name(client, url)
        assert full_name == "Full Arome Beer Name"

if __name__ == "__main__":
    async def main():
        url = "https://www.arome.jp/products/detail.php?product_id=5725"
        print(f"URL: {url}\n")
        print("詳細ページから商品名を取得中...\n")
        ssl_ctx = get_legacy_ssl_context()
        async with httpx.AsyncClient(verify=ssl_ctx, timeout=30.0) as client:
            full_name = await fetch_full_name(client, url)
            if full_name:
                print(f"✓ 取得成功: {full_name}")
            else:
                print("✗ 取得失敗")
    asyncio.run(main())

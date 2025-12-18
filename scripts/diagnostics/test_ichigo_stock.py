import asyncio
import httpx
from app.services.stock_checker import check_stock_for_url

async def main():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    urls = [
        ("https://151l.shop/?pid=176174163", "Expected: In Stock"),
        ("https://151l.shop/?pid=189666586", "Expected: Sold Out")
    ]
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for url, expected in urls:
            print(f"Checking {url} ({expected})...")
            result = await check_stock_for_url(client, url, "一期一会～る")
            print(f"Result: {result}\n")

if __name__ == "__main__":
    asyncio.run(main())

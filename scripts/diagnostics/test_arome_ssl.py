import httpx
import ssl
import asyncio

async def test_arome():
    url = "https://www.arome.jp/products/detail.php?product_id=6743"
    print(f"Testing {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Strategy 1: SECLEVEL=1
    print("\n--- Strategy 1: SECLEVEL=1 ---")
    try:
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        async with httpx.AsyncClient(verify=ctx, headers=headers) as client:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
    except Exception as e:
        print(f"Error 1: {e}")

    # Strategy 2: verify=False
    print("\n--- Strategy 2: verify=False ---")
    try:
        async with httpx.AsyncClient(verify=False, headers=headers) as client:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
    except Exception as e:
        print(f"Error 2: {e}")

if __name__ == "__main__":
    asyncio.run(test_arome())


import asyncio
import httpx

async def fetch_html():
    url = "https://151l.shop/?mode=cate&cbid=2463806&csid=0&sort=n"
    async with httpx.AsyncClient() as client:
        # Mimic browser headers more closely
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }
        response = await client.get(url, headers=headers)
        # Try generic decoding
        content = response.content.decode('utf-8', errors='replace')
        
        # Save to file
        with open('debug_ichigo.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Saved debug_ichigo.html")
        
        # Quick check for selector string
        if 'thum_data_area' in content:
            print("Found 'thum_data_area' in HTML")
        else:
            print("Did NOT find 'thum_data_area' in HTML")

if __name__ == "__main__":
    asyncio.run(fetch_html())

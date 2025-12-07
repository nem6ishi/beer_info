import requests
from bs4 import BeautifulSoup

url = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

resp = requests.get(url, headers=headers)
print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    soup = BeautifulSoup(resp.text, 'lxml')
    
    # Try to find requested fields
    name = soup.select_one('.name h1')
    brewery = soup.select_one('.name .brewery')
    style = soup.select_one('.name .style')
    
    # ABV, IBU, RATING are usually in .details or .stats
    # Let's just print the text of likely containers to parse mentally
    print(f"Name H1: {name.get_text(strip=True) if name else 'Not Found'}")
    print(f"Brewery: {brewery.get_text(strip=True) if brewery else 'Not Found'}")
    print(f"Style: {style.get_text(strip=True) if style else 'Not Found'}")
    
    details_block = soup.select_one('.details')
    if details_block:
        print("--- DETAILS BLOCK ---")
        print(details_block.prettify())

    stats_block = soup.select_one('.stats')
    if stats_block:
        print("--- STATS BLOCK ---")
        print(stats_block.prettify())

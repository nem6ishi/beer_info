import requests
from bs4 import BeautifulSoup
import sys

def search_brewery_beers(brewery_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"{brewery_url}/beer"
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        print(f"Failed to load {url}")
        return
    
    soup = BeautifulSoup(resp.text, 'lxml')
    beers = soup.select('.beer-item')
    print(f"Found {len(beers)} beers:")
    for b in beers:
        name = b.select_one('.name a').text.strip()
        link = b.select_one('.name a')['href']
        print(f"- {name} (https://untappd.com{link})")

if __name__ == '__main__':
    search_brewery_beers("https://untappd.com/CRAFTROCK")

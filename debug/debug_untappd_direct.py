import requests
from bs4 import BeautifulSoup
import urllib.parse

def test_untappd_direct(query):
    print(f"--- Testing Direct Untappd Search: {query} ---")
    encoded_query = urllib.parse.quote(query)
    url = f"https://untappd.com/search?q={encoded_query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            title = soup.title.string.strip() if soup.title else "No Title"
            print(f"Title: {title}")
            
            # Check for beer results
            results = soup.select('.beer-item')
            print(f"Found {len(results)} beer items.")
            for i, res in enumerate(results[:3]):
                name_tag = res.select_one('.name a')
                if name_tag:
                    print(f"Result {i+1}: {name_tag.get_text()} -> {name_tag.get('href')}")
        else:
            print("Access non-200.")
    except Exception as e:
        print(f"Error: {e}")
    print("\n")

def test_lite_ddg(query):
    print(f"--- Testing Lite DDG: {query} ---")
    url = "https://lite.duckduckgo.com/lite/"
    data = {'q': query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
             soup = BeautifulSoup(resp.text, 'lxml')
             results = soup.select('table.result-table') # parsing lite is tricky, check structure
             if not results:
                 # Lite output structure varies, might be simple links
                 links = soup.select('a.result-link')
                 print(f"Found {len(links)} result links.")
                 for i, link in enumerate(links[:3]):
                     print(f"Result {i+1}: {link.get_text()} -> {link.get('href')}")
    except Exception as e:
        print(f"Error: {e}")
    print("\n")

if __name__ == "__main__":
    q = 'Inkhorn Brewing UGUISU'
    test_untappd_direct(q)
    test_lite_ddg(f'site:untappd.com/b/ "{q}"')

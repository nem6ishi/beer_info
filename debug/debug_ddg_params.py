import requests
from bs4 import BeautifulSoup

def search(query):
    url = "https://html.duckduckgo.com/html/"
    data = {'q': query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://html.duckduckgo.com/"
    }
    
    print(f"--- Query: {query} ---")
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        print(f"Status Code: {resp.status_code}")
        
        soup = BeautifulSoup(resp.text, 'lxml')
        title = soup.title.string if soup.title else "No Title"
        print(f"Page Title: {title}")
        
        results = soup.find_all('div', class_='result')
        print(f"Found {len(results)} results.")
        
        for i, res in enumerate(results[:3]):
            link = res.find('a', class_='result__a')
            if link:
                href = link.get('href')
                text = link.get_text(strip=True)
                print(f"Result {i+1}: {text} -> {href}")
                
    except Exception as e:
        print(f"Error: {e}")
    print("\n")

if __name__ == "__main__":
    queries = [
        'site:untappd.com/b/ "Inkhorn Brewing" "UGUISU"',
        'site:untappd.com/b/ Inkhorn Brewing UGUISU',
        'Inkhorn Brewing UGUISU site:untappd.com',
        'Inkhorn Brewing UGUISU untappd'
    ]
    
    for q in queries:
        search(q)

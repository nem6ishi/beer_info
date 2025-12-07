import requests
from bs4 import BeautifulSoup

def search_ddg_html(brewery, beer):
    query = f'site:untappd.com/b/ "{brewery}" "{beer}"'
    print(f"Searching DDG HTML: {query}")
    
    url = "https://html.duckduckgo.com/html/"
    data = {'q': query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://html.duckduckgo.com/"
    }
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # DDG HTML results are usually in div.result
            results = soup.find_all('div', class_='result')
            print(f"Found {len(results)} raw results")
            
            for res in results:
                link = res.find('a', class_='result__a')
                if link:
                    href = link.get('href')
                    print(f"  LINK: {href}")
                    if "untappd.com/b/" in href:
                        print(f"  MATCH: {href}")
                        return href
                        
    except Exception as e:
        print(f"Error: {e}")

search_ddg_html("Inkhorn Brewing", "UGUISU")
search_ddg_html("Smog City", "Supercell")

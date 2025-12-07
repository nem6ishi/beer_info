import requests
from bs4 import BeautifulSoup
import re

def search_google_manual(query):
    print(f"Manual Searching: {query}")
    try:
        url = "https://www.google.com/search"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            # Save HTML to analyze structure
            with open("debug_google_search.html", "w") as f:
                f.write(resp.text)
            print("Saved debug_google_search.html")

            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Print first 5 links found to verify structure
            print("--- First 5 Links ---")
            for i, link in enumerate(soup.find_all('a')[:5]):
                print(f"{i}: {link.get('href')}")
            
            # Look for all links
            links = soup.find_all('a')
            for link in links:
                href = link.get('href')
                if not href: continue
                
                # Check for direct Untappd links
                if "untappd.com/b/" in href:
                    print(f"FOUND DIRECT: {href}")
                    return href
                
                # Check for wrapped links (/url?q=...)
                if "/url?q=" in href:
                    parts = href.split("/url?q=")
                    if len(parts) > 1:
                        actual_url = parts[1].split("&")[0]
                        if "untappd.com/b/" in actual_url:
                            print(f"FOUND WRAPPED: {actual_url}")
                            return actual_url
            
            print("No valid external untappd links found.")
            
    except Exception as e:
        print(f"Error: {e}")

brewery = "Inkhorn Brewing"
beer = "UGUISU"

# Try simple query
search_google_manual(f'site:untappd.com/b/ {brewery} {beer}')
search_google_manual(f'{brewery} {beer} site:untappd.com')

from googlesearch import search

def test_search(query):
    print(f"Testing query: {query}")
    try:
        results = search(query, num_results=1, advanced=True, sleep_interval=1.0)
        found = False
        for result in results:
            print(f"  FOUND: {result.url}")
            found = True
        if not found:
            print("  NO RESULTS")
    except Exception as e:
        print(f"  ERROR: {e}")

brewery = "Inkhorn Brewing"
beer = "UGUISU"

# 5. Generic test
print("--- Generic Test ---")
test_search('untappd')

# 7. Connectivity Test
print("--- Connectivity Test ---")
import requests
try:
    resp = requests.get('https://www.google.com/search?q=test', headers={'User-Agent': 'Mozilla/5.0'})
    print(f"Status Code: {resp.status_code}")
    print(f"Content Length: {len(resp.text)}")
    if "CAPTCHA" in resp.text or "unusual traffic" in resp.text:
        print("  BLOCK: CAPTCHA detected")
    else:
        print("  OK: Google accessible (checking for results)")
        # Simple check if search results exist in HTML
        if "test" in resp.text:
            print("  OK: 'test' found in response")
except Exception as e:
    print(f"  ERROR: {e}")

from duckduckgo_search import DDGS

def test_search(query):
    print(f"Testing DDG query: {query}")
    try:
        results = DDGS().text(query, max_results=1)
        found = False
        for result in results:
            print(f"  FOUND: {result.get('href')}")
            found = True
        if not found:
            print("  NO RESULTS")
    except Exception as e:
        print(f"  ERROR: {e}")

brewery = "Inkhorn Brewing"
beer = "UGUISU"

# Natural language query
test_search(f'{brewery} {beer} untappd')

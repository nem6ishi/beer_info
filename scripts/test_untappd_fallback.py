import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import get_untappd_url

if __name__ == "__main__":
    # Search for something likely not to match a single beer directly or at all
    # "NonExistentBrewery NonExistentBeerXYZ"
    brewery = "NonExistentBrewery"
    beer = "NonExistentBeerXYZ"
    
    print(f"Testing fallback for: {brewery} {beer}")
    url = get_untappd_url(brewery, beer)
    print(f"Result URL: {url}")
    
    expected_base = "https://untappd.com/search?q="
    if url and url.startswith(expected_base):
        print("SUCCESS: Returned search URL as fallback.")
    else:
        print(f"FAILURE: Did not return search URL. Got: {url}")

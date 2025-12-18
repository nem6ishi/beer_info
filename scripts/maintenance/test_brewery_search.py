import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.services.untappd_searcher import get_untappd_url

logging.basicConfig(level=logging.INFO)

# Test case: West Coast Brewing - Red IPA
# User says normal search fails, but brewery page works.
brewery = "West Coast Brewing"
beer = "Red IPA"
brewery_url = "https://untappd.com/West_Coast_Brewing"

print(f"🚀 Testing prioritized brewery-specific search for: {brewery} - {beer}")
url = get_untappd_url(brewery, beer, brewery_url=brewery_url)
print(f"🏁 Result: {url}")

expected = "https://untappd.com/b/west-coast-brewing-red-ipa/6488293"
if url == expected:
    print("✅ SUCCESS: Found correct URL!")
else:
    print(f"❌ FAILURE: Expected {expected} but got {url}")

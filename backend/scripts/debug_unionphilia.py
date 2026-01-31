import logging
import asyncio
from backend.src.services.untappd.searcher import get_untappd_url, validate_beer_match, validate_brewery_match
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)

async def debug():
    # Test cases
    brewery = "Totopia Brewery x Teenage Brewing"
    beer = "Unionphilia"
    
    print(f"\n--- Testing Search for: {brewery} / {beer} ---")
    result = get_untappd_url(brewery, beer)
    print(f"Result URL: {result['url']}")
    print(f"Success: {result['success']}")
    print(f"Reason: {result['failure_reason']}")

    # Check normalization directly
    from backend.src.services.untappd.searcher import normalize_for_comparison
    print(f"\n--- Normalization Check ---")
    print(f"Unionphilia -> {normalize_for_comparison('Unionphilia')}")
    print(f"Tonephilia -> {normalize_for_comparison('Tonephilia')}")

if __name__ == "__main__":
    asyncio.run(debug())

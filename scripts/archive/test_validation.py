
import sys
import os
from bs4 import BeautifulSoup
import logging

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.untappd_searcher import validate_brewery_match, normalize_for_comparison, BREWERY_ALIASES

# Configure logging to see debug output
logging.basicConfig(level=logging.DEBUG)

def test_normalization():
    print("--- Testing Normalization ---")
    print(f"'CRAFT ROCK' -> '{normalize_for_comparison('CRAFT ROCK')}'")
    print(f"'CRAFTROCK'  -> '{normalize_for_comparison('CRAFTROCK')}'")
    assert normalize_for_comparison('CRAFT ROCK') == normalize_for_comparison('CRAFTROCK')
    print("✅ Normalization works for CRAFT ROCK")

def test_validation():
    print("\n--- Testing Validation ---")
    
    # Mock BeautifulSoup element
    html = '<div class="beer-item"><p class="name"><a href="#">Beer</a></p><p class="brewery"><a href="#">CRAFTROCK Brewing</a></p></div>'
    soup = BeautifulSoup(html, 'lxml')
    item = soup.select_one('.beer-item')
    
    # Case 1: Exact Match (Normalized)
    expected = "CRAFT ROCK Brewing"
    print(f"Testing: Expected='{expected}' vs Result='CRAFTROCK Brewing'")
    result = validate_brewery_match(item, expected)
    print(f"Match: {result}")
    assert result is True
    
    # Case 2: Alias Match
    # "Shiga Kogen" -> Alias "Tamamura Honten"
    # Result HTML has "Tamamura Honten Co."
    html2 = '<div class="beer-item"><p class="brewery">Tamamura Honten Co.</p></div>'
    soup2 = BeautifulSoup(html2, 'lxml')
    item2 = soup2.select_one('.beer-item')
    
    expected2 = "Shiga Kogen"
    print(f"Testing: Expected='{expected2}' vs Result='Tamamura Honten Co.'")
    result2 = validate_brewery_match(item2, expected2)
    print(f"Match: {result2}")
    assert result2 is True

if __name__ == "__main__":
    test_normalization()
    test_validation()

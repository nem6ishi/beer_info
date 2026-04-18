
import sys
from pathlib import Path

# Add the project root to sys.path
root = Path("/Users/nemu/Library/CloudStorage/GoogleDrive-nem6ishi@gmail.com/マイドライブ/play/beer_info")
sys.path.append(str(root))

from backend.src.services.untappd.searcher import get_untappd_url
import logging

logging.basicConfig(level=logging.INFO)

def test_search(brewery, beer, beer_jp=None):
    print(f"\n--- Testing Search: {brewery} / {beer} ({beer_jp}) ---")
    result = get_untappd_url(
        brewery_name=brewery,
        beer_name=beer,
        beer_name_jp=beer_jp
    )
    print(f"Result: {result}")

if __name__ == "__main__":
    # Test case 1: Correct brewery name vs Untappd name
    test_search("渥美半島醸造", "WANAKA")

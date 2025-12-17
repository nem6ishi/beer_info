import os
import sys

# Add project root to sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
sys.path.append(root_dir)

from app.services.untappd_searcher import search_brewery

def debug_search():
    query = "And Beer"
    print(f"Searching brewery: '{query}'...")
    
    url = search_brewery(query)
    
    print(f"Result URL: {url}")
    
    if "timmermans" in str(url).lower():
        print("CONFIRMED: Search returns Timmermans!")
    elif "and-beer" in str(url).lower():
        print("RESULT IS CORRECT (And Beer). Issue might be intermittent or fixed.")
    else:
        print("RESULT IS DIFFERENT.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    debug_search()

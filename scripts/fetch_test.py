import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers.runner import run_scrapers

import asyncio

if __name__ == "__main__":
    print("Fetching 1 beer from each site...")
    asyncio.run(run_scrapers(limit=1))
    print("Done.")

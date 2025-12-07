import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers.runner import run_scrapers


if __name__ == "__main__":
    print("Fetching 1 beer from each site to refresh data with new Untappd logic...")
    # This will use the new get_untappd_url in runner.py
    asyncio.run(run_scrapers(limit=1))
    print("Done.")

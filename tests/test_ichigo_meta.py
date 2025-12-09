import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scrapers import ichigo_ichie

async def main():
    print("Testing Ichigo Ichie scraper return value...")
    # Run with limit=3, reverse=True to trigger the logic
    result = await ichigo_ichie.scrape_ichigo_ichie(limit=3, reverse=True)
    
    print("\n-------------------")
    print(f"Type: {type(result)}")
    if isinstance(result, tuple):
        items, max_page = result
        print(f"Items count: {len(items)}")
        print(f"Max Page: {max_page}")
    else:
        print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
from app.core.db import get_supabase_client

async def main():
    supabase = get_supabase_client()
    keyword = "Tonephilia"
    print(f"Searching for beers with keyword: {keyword}")
    
    response = supabase.table('beer_info_view').select('*').ilike('name', f'%{keyword}%').execute()
    beers = response.data
    
    if not beers:
        print("No beers found.")
        return
        
    for beer in beers:
        print("-" * 50)
        print(f"Name: {beer.get('name')}")
        print(f"Brewery (EN): {beer.get('brewery_name_en')}")
        print(f"Beer (EN):    {beer.get('beer_name_en')}")
        print(f"Untappd URL:  {beer.get('untappd_url')}")
        print(f"Shop:         {beer.get('shop')}")
        print(f"URL:          {beer.get('url')}")

if __name__ == "__main__":
    asyncio.run(main())

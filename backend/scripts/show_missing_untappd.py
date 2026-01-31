import asyncio
from backend.src.core.db import get_supabase_client

async def main():
    supabase = get_supabase_client()
    
    # Get 50 beers missing untappd_url, ordered by first_seen DESC
    response = supabase.table('beer_info_view') \
        .select('name, shop, first_seen, brewery_name_en, beer_name_en') \
        .is_('untappd_url', 'null') \
        .order('first_seen', desc=True) \
        .limit(50) \
        .execute()
    
    beers = response.data
    
    if not beers:
        print("Untappd情報が未取得なビールは見つかりませんでした。")
        return

    print(f"{'No':<3} | {'First Seen':<20} | {'Shop':<12} | {'Name'}")
    print("-" * 100)
    for i, beer in enumerate(beers, 1):
        name = beer['name'][:60]
        shop = beer['shop']
        first_seen = beer['first_seen']
        print(f"{i:<3} | {first_seen:<20} | {shop:<12} | {name}")

if __name__ == "__main__":
    asyncio.run(main())

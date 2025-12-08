#!/usr/bin/env python3
"""
Simple script to view Supabase data locally
"""
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Get Supabase credentials
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file")
        sys.exit(1)
    
    # Create Supabase client
    supabase = create_client(supabase_url, supabase_key)
    
    # Get command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
    else:
        command = 'stats'
    
    if command == 'stats':
        # Show statistics
        print("\n📊 Database Statistics\n" + "="*50)
        
        # Total beers
        total = supabase.table('beers').select('id', count='exact').execute()
        print(f"Total beers: {total.count:,}")
        
        # Beers by shop
        shops = ['BEER VOLTA', 'ちょうせいや', '一期一会～る']
        print("\nBeers by shop:")
        for shop in shops:
            result = supabase.table('beers').select('id', count='exact').eq('shop', shop).execute()
            print(f"  {shop}: {result.count:,}")
        
        # Beers with display_timestamp
        with_ts = supabase.table('beers').select('id', count='exact').not_.is_('display_timestamp', 'null').execute()
        print(f"\nBeers with display_timestamp: {with_ts.count:,}")
        
        # Beers with Untappd data
        with_untappd = supabase.table('beers').select('id', count='exact').not_.is_('untappd_rating', 'null').execute()
        print(f"Beers with Untappd rating: {with_untappd.count:,}")
        
    elif command == 'recent':
        # Show recent beers
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        print(f"\n🆕 Most Recent {limit} Beers (by display_timestamp)\n" + "="*50)
        
        result = supabase.table('beers').select('name, shop, price, display_timestamp').not_.is_('display_timestamp', 'null').order('display_timestamp', desc=True).limit(limit).execute()
        
        for i, beer in enumerate(result.data, 1):
            print(f"\n{i}. [{beer['shop']}] {beer['name'][:60]}")
            print(f"   Price: {beer['price']}")
            print(f"   Timestamp: {beer['display_timestamp']}")
    
    elif command == 'shop':
        # Show beers from specific shop
        if len(sys.argv) < 3:
            print("Usage: python scripts/view_data.py shop <shop_name> [limit]")
            print("Shop names: 'BEER VOLTA', 'ちょうせいや', '一期一会～る'")
            sys.exit(1)
        
        shop_name = sys.argv[2]
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        
        print(f"\n🏪 {shop_name} - First {limit} Beers\n" + "="*50)
        
        result = supabase.table('beers').select('name, price, stock_status, display_timestamp').eq('shop', shop_name).order('display_timestamp', desc=True).limit(limit).execute()
        
        for i, beer in enumerate(result.data, 1):
            print(f"\n{i}. {beer['name'][:60]}")
            print(f"   Price: {beer['price']}")
            print(f"   Status: {beer['stock_status']}")
            if beer['display_timestamp']:
                print(f"   Timestamp: {beer['display_timestamp']}")
    
    elif command == 'search':
        # Search beers
        if len(sys.argv) < 3:
            print("Usage: python scripts/view_data.py search <query>")
            sys.exit(1)
        
        query = sys.argv[2]
        print(f"\n🔍 Search Results for '{query}'\n" + "="*50)
        
        result = supabase.table('beers').select('name, shop, price, stock_status').ilike('name', f'%{query}%').limit(20).execute()
        
        if not result.data:
            print("No results found.")
        else:
            for i, beer in enumerate(result.data, 1):
                print(f"\n{i}. [{beer['shop']}] {beer['name']}")
                print(f"   Price: {beer['price']} | Status: {beer['stock_status']}")
    
    else:
        print("Unknown command. Available commands:")
        print("  stats              - Show database statistics")
        print("  recent [limit]     - Show recent beers (default: 10)")
        print("  shop <name> [limit] - Show beers from specific shop")
        print("  search <query>     - Search beers by name")

if __name__ == '__main__':
    main()

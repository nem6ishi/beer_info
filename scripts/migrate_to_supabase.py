#!/usr/bin/env python3
"""
Migration script to populate Supabase from beers.json
Run this once to migrate existing data to the cloud database
"""
import json
import os
import sys
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Get Supabase credentials from environment
SUPABASE_URL = (os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL') or '').strip()
SUPABASE_KEY = (os.getenv('SUPABASE_SERVICE_KEY') or '').strip()  # Use service role key for write access

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE URL and SUPABASE_SERVICE_KEY environment variables must be set")
    print("\nUsage:")
    print("  export SUPABASE_URL='https://your-project.supabase.co'")
    print("  export SUPABASE_SERVICE_KEY='your-service-role-key'")
    print("  python scripts/migrate_to_supabase.py")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEERS_FILE = os.path.join(BASE_DIR, "data", "beers.json")
BREWERIES_FILE = os.path.join(BASE_DIR, "data", "breweries.json")


def parse_timestamp(ts_str):
    """Convert Japanese timestamp string to ISO format"""
    if not ts_str:
        return None
    try:
        # Parse format like "2025/12/07 12:33:29"
        dt = datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
        return dt.isoformat()
    except:
        return None


def migrate_beers(supabase: Client):
    """Migrate beers from JSON to Supabase"""
    print(f"\n{'='*70}")
    print("📦 Migrating Beers")
    print(f"{'='*70}")
    
    if not os.path.exists(BEERS_FILE):
        print(f"❌ Error: {BEERS_FILE} not found")
        return
    
    with open(BEERS_FILE, 'r', encoding='utf-8') as f:
        beers = json.load(f)
    
    print(f"📂 Loaded {len(beers)} beers from {BEERS_FILE}")
    
    # Convert beers to Supabase format
    processed_beers = []
    for beer in beers:
        processed_beer = {
            'url': beer.get('url'),
            'name': beer.get('name'),
            'price': beer.get('price'),
            'image': beer.get('image'),
            'stock_status': beer.get('stock_status'),
            'shop': beer.get('shop'),
            
            # Timestamps
            'first_seen': parse_timestamp(beer.get('first_seen')),
            'last_seen': parse_timestamp(beer.get('last_seen')),
            'available_since': parse_timestamp(beer.get('available_since')),
            'restocked_at': parse_timestamp(beer.get('restocked_at')),
            'scrape_timestamp': parse_timestamp(beer.get('scrape_timestamp')),
            'scrape_order': beer.get('scrape_order'),
            
            # Gemini data
            'brewery_name_jp': beer.get('brewery_name_jp'),
            'brewery_name_en': beer.get('brewery_name_en'),
            'beer_name_jp': beer.get('beer_name_jp'),
            'beer_name_en': beer.get('beer_name_en'),
            
            # Untappd data
            'untappd_url': beer.get('untappd_url'),
            'untappd_beer_name': beer.get('untappd_beer_name'),
            'untappd_brewery_name': beer.get('untappd_brewery_name'),
            'untappd_style': beer.get('untappd_style'),
            'untappd_abv': beer.get('untappd_abv'),
            'untappd_ibu': beer.get('untappd_ibu'),
            'untappd_rating': beer.get('untappd_rating'),
            'untappd_rating_count': beer.get('untappd_rating_count'),
            'untappd_fetched_at': beer.get('untappd_fetched_at'),
        }
        
        # Remove None values
        processed_beer = {k: v for k, v in processed_beer.items() if v is not None}
        processed_beers.append(processed_beer)
    
    # Batch insert (Supabase has a limit, so we'll do batches of 1000)
    batch_size = 1000
    total_inserted = 0
    
    for i in range(0, len(processed_beers), batch_size):
        batch = processed_beers[i:i + batch_size]
        print(f"  🔄 Inserting batch {i // batch_size + 1} ({len(batch)} beers)...")
        
        try:
            result = supabase.table('beers').upsert(batch, on_conflict='url').execute()
            total_inserted += len(batch)
            print(f"  ✅ Inserted {len(batch)} beers")
        except Exception as e:
            print(f"  ❌ Error inserting batch: {e}")
            continue
    
    print(f"\n✅ Migration complete: {total_inserted}/{len(beers)} beers inserted")


def migrate_breweries(supabase: Client):
    """Migrate breweries from JSON to Supabase"""
    print(f"\n{'='*70}")
    print("🏭 Migrating Breweries")
    print(f"{'='*70}")
    
    if not os.path.exists(BREWERIES_FILE):
        print(f"⚠️  {BREWERIES_FILE} not found, skipping breweries migration")
        return
    
    with open(BREWERIES_FILE, 'r', encoding='utf-8') as f:
        breweries_data = json.load(f)
    
    breweries = breweries_data.get('breweries', [])
    print(f"📂 Loaded {len(breweries)} breweries from {BREWERIES_FILE}")
    
    # Convert breweries to Supabase format
    processed_breweries = []
    for brewery in breweries:
        processed_brewery = {
            'name_en': brewery.get('name_en'),
            'name_jp': brewery.get('name_jp'),
            'aliases': brewery.get('aliases', []),
        }
        processed_breweries.append(processed_brewery)
    
    # Insert all breweries
    try:
        result = supabase.table('breweries').insert(processed_breweries).execute()
        print(f"✅ Inserted {len(processed_breweries)} breweries")
    except Exception as e:
        print(f"❌ Error inserting breweries: {e}")


def main():
    print("=" * 70)
    print("🚀 Supabase Migration Script")
    print("=" * 70)
    print(f"Supabase URL: {SUPABASE_URL}")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Migrate data
    migrate_beers(supabase)
    migrate_breweries(supabase)
    
    # Show stats
    print(f"\n{'='*70}")
    print("📊 Final Statistics")
    print(f"{'='*70}")
    
    try:
        beer_count = supabase.table('beers').select('*', count='exact', head=True).execute()
        print(f"  Total beers in Supabase: {beer_count.count}")
        
        brewery_count = supabase.table('breweries').select('*', count='exact', head=True).execute()
        print(f"  Total breweries in Supabase: {brewery_count.count}")
    except Exception as e:
        print(f"  ❌ Error fetching stats: {e}")
    
    print(f"\n{'='*70}")
    print("✨ Migration completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()

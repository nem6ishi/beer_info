#!/usr/bin/env python3
"""
Untappd-only enrichment script for Supabase
Enriches beers that already have Gemini data but missing Untappd info
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import get_untappd_url, scrape_beer_details
from app.services.brewery_manager import BreweryManager

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

# Get credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)


async def process_beer(beer, supabase, brewery_manager=None):
    """
    Process a single beer: search Untappd, scrape details, update DB, and optionally update brewery manager.
    """
    updates = {}
    
    # Extract brewery and beer names
    brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
    
    if not brewery or not beer_name:
        print(f"  ⚠️  Missing brewery or beer name - skipping")
        return None
    
    try:
        untappd_url = beer.get('untappd_url')
        
        # Use existing URL if valid, otherwise search
        if untappd_url and "untappd.com" in untappd_url:
            print(f"  🔗 Using existing URL: {untappd_url}")
        else:
            print(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
            untappd_url = get_untappd_url(brewery, beer_name)
        
        if untappd_url:
            updates['untappd_url'] = untappd_url
            print(f"  ✅ Found URL: {untappd_url}")
            
            # If it's a direct beer page, scrape details
            if "untappd.com/b/" in untappd_url:
                await asyncio.sleep(2)  # Rate limiting
                print(f"  🔄 Scraping beer details...")
                
                try:
                    details = scrape_beer_details(untappd_url)
                    if details:
                        updates.update(details)
                        updates['untappd_fetched_at'] = datetime.now(timezone.utc).isoformat()
                        print(f"  ✅ Details scraped:")
                        print(f"     Style: {details.get('untappd_style', 'N/A')}")
                        print(f"     ABV: {details.get('untappd_abv', 'N/A')}, IBU: {details.get('untappd_ibu', 'N/A')}")
                        print(f"     Rating: {details.get('untappd_rating', 'N/A')} ({details.get('untappd_rating_count', 'N/A')})")
                    else:
                        print(f"  ⚠️  Could not scrape details from page")
                except Exception as detail_error:
                    print(f"  ⚠️  Error scraping details: {detail_error}")
        else:
            print(f"  ❌ Untappd URL not found")
            updates['untappd_url'] = "NOT_FOUND" 
    
    except Exception as e:
        print(f"  ❌ Untappd search error: {e}")
        return None
    
    # Update database
    if updates:
        try:
            supabase.table('beers').update(updates).eq('id', beer['id']).execute()
            print(f"  💾 Updated database")
            
            # Immediate brewery update if manager is provided
            if brewery_manager:
                # Create a temporary beer dict with updates applied to extract brewery info
                enriched_beer = beer.copy()
                enriched_beer.update(updates)
                
                # We need ensure untappd_brewery_name is present if we scraped it
                # It comes from 'details' which is merged into updates.
                
                new_count = brewery_manager.extract_breweries_from_beers([enriched_beer])
                if new_count > 0:
                    brewery_manager.save_breweries()
                    print(f"  🏭 Saved new brewery info")
                    
        except Exception as e:
            print(f"  ❌ Database update error: {e}")
            return None
            
    return updates


async def enrich_untappd(limit: int = 50):
    """Enrich beers with Untappd data only. Loops until all processed."""
    print("=" * 70)
    print("🍺 Untappd Enrichment (Supabase)")
    print("=" * 70)
    print(f"Target: All beers with Gemini data but no Untappd URL (Batch size: {limit})")
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Initialize Brewery Manager for batch updates
    brewery_manager = BreweryManager()
    
    total_processed = 0
    total_untappd_found = 0
    total_details_scraped = 0
    total_errors = 0
    
    batch_size = 1000 if limit > 1000 else limit
    
    while True:
        # Get beers that have Gemini data but no Untappd URL
        print(f"\n📂 Loading batch of beers from Supabase (Limit: {batch_size})...")
        response = supabase.table('beers') \
            .select('*') \
            .not_.is_('brewery_name_en', None) \
            .is_('untappd_rating', None) \
            .order('first_seen', desc=True) \
            .limit(batch_size) \
            .execute()
        
        # Also try beers with brewery_name_jp but no brewery_name_en
        if len(response.data) < batch_size:
            response2 = supabase.table('beers') \
                .select('*') \
                .not_.is_('brewery_name_jp', None) \
                .is_('untappd_rating', None) \
                .order('first_seen', desc=True) \
                .limit(batch_size - len(response.data)) \
                .execute()
            
            # Merge results, avoiding duplicates
            existing_ids = {b['id'] for b in response.data}
            for beer in response2.data:
                if beer['id'] not in existing_ids:
                    response.data.append(beer)
        
        beers = response.data
        print(f"  Found {len(beers)} beers needing Untappd enrichment")
        
        if not beers:
            print("\n✨ No more beers need Untappd enrichment!")
            break
        
        # Process beers
        for i, beer in enumerate(beers, 1):
            print(f"\n{'='*70}")
            print(f"[Batch {i}/{len(beers)} | Total {total_processed + i}] Processing: {beer.get('name', 'Unknown')[:60]}")
            print(f"{'='*70}")
            
            updates = await process_beer(beer, supabase, brewery_manager)
            
            if updates:
                if 'untappd_url' in updates and updates['untappd_url'] != "NOT_FOUND":
                    total_untappd_found += 1
                if 'untappd_style' in updates:
                    total_details_scraped += 1
            else:
                # If None returned, it's an error or skip. 
                # Could be error (update failed) or skip (missing names).
                pass
                
            await asyncio.sleep(1)  # Rate limiting between searches
            
        total_processed += len(beers)

    # Final stats
    print(f"\n{'='*70}")
    print("📈 Final Statistics")
    print(f"{'='*70}")
    print(f"  Total processed: {total_processed}")
    print(f"  Untappd URLs found: {total_untappd_found}")
    print(f"  Details scraped: {total_details_scraped}")
    print(f"  Errors: {total_errors}")
    
    # Update brewery database
    print(f"\n🏭 Updating brewery database...")
    brewery_manager = BreweryManager()
    
    # Get all beers with Untappd data to extract breweries
    all_enriched = supabase.table('beers') \
        .select('untappd_brewery_name, brewery_name_en, brewery_name_jp') \
        .not_.is_('untappd_brewery_name', None) \
        .execute()
    
    new_breweries = brewery_manager.extract_breweries_from_beers(all_enriched.data)
    if new_breweries > 0:
        brewery_manager.save_breweries()
        print(f"  ✅ Added {new_breweries} new breweries")
    else:
        print(f"  ℹ️  No new breweries to add")
    
    stats = brewery_manager.get_stats()
    print(f"  📊 Total breweries: {stats['total_breweries']}")
    
    print(f"\n  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'='*70}")
    print("✨ Untappd enrichment completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Untappd in Supabase')
    parser.add_argument('--limit', type=int, default=1000, help='Batch size (default 1000)')
    
    args = parser.parse_args()
    
    asyncio.run(enrich_untappd(limit=args.limit))

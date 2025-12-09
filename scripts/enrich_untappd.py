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
    Process a single beer: search Untappd, scrape details, update DB (untappd_data, scraped_beers, gemini_data).
    """
    scraped_updates = {} # Updates for scraped_beers table (link)
    untappd_payload = {} # Updates for untappd_data table (master info)
    gemini_updates = {}  # Updates for gemini_data table (persistence)
    
    # Extract brewery and beer names
    brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
    beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
    
    if not brewery or not beer_name:
        print(f"  ⚠️  Missing brewery or beer name - skipping")
        return None
    
    try:
        untappd_url = beer.get('untappd_url')
        
        # 1. OPTIMIZATION: Check if we have this URL in gemini_data already (if not passed in beer)
        # The view should have it, but if it was just added to the schema, it might be null in view but passed here?
        # Actually, let's rely on what's passed or search.
        
        # Use existing URL if valid, otherwise search
        if untappd_url and "untappd.com" in untappd_url:
            print(f"  🔗 Using existing URL: {untappd_url}")
        else:
            print(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
            untappd_url = get_untappd_url(brewery, beer_name)
        
        if untappd_url:
            scraped_updates['untappd_url'] = untappd_url
            gemini_updates['untappd_url'] = untappd_url # PERSISTENCE
            untappd_payload['untappd_url'] = untappd_url # PK
            
            print(f"  ✅ Found URL: {untappd_url}")
            
            # 2. OPTIMIZATION: Check if this URL already exists in untappd_data table
            # If so, we don't need to re-scrape attributes (style, abv, etc.)
            existing_entry = supabase.table('untappd_data').select('untappd_url').eq('untappd_url', untappd_url).execute()
            
            if existing_entry.data:
                print(f"  💾 Data already exists in untappd_data. Skipping scrape.")
                untappd_payload = {} # No content updates needed for master table
                # We still proceed to update links (scraped_beers, gemini_data)
            
            # If not in DB, scrape details
            elif "untappd.com/b/" in untappd_url:
                await asyncio.sleep(2)  # Rate limiting
                print(f"  🔄 Scraping beer details...")
                
                try:
                    details = scrape_beer_details(untappd_url)
                    if details:
                        # Map details to untappd_data columns
                        untappd_payload.update({
                            'beer_name': details.get('untappd_beer_name'),
                            'brewery_name': details.get('untappd_brewery_name'),
                            'style': details.get('untappd_style'),
                            'abv': details.get('untappd_abv'),
                            'ibu': details.get('untappd_ibu'),
                            'rating': details.get('untappd_rating'),
                            'rating_count': details.get('untappd_rating_count'),
                            'image_url': details.get('untappd_label'),
                            'fetched_at': datetime.now(timezone.utc).isoformat()
                        })

                        print(f"  ✅ Details scraped: {details.get('untappd_style', 'N/A')}")
                    else:
                        print(f"  ⚠️  Could not scrape details from page")
                        untappd_payload['fetched_at'] = datetime.now(timezone.utc).isoformat()
                except Exception as detail_error:
                    print(f"  ⚠️  Error scraping details: {detail_error}")
        else:
            print(f"  ❌ Untappd URL not found")
            return None
    
    except Exception as e:
        print(f"  ❌ Untappd search error: {e}")
        return None
    
    # Update databases
    success = False
    
    # 1. Upsert to untappd_data (only if we have new payload)
    if untappd_payload:
        try:
            supabase.table('untappd_data').upsert(untappd_payload).execute()
            print(f"  💾 Saved to untappd_data table")
            success = True
        except Exception as e:
            print(f"  ❌ Error saving to untappd_data: {e}")

    # 2. Update gemini_data (PERSISTENCE)
    # Be careful: gemini_data PK is 'url' (product url). We need that from 'beer' dict.
    if gemini_updates and beer.get('url'):
        try:
            # We used to upsert entire gemini payload, but here we just want to update one field?
            # 'gemini_data' has 'url' as PK.
            supabase.table('gemini_data').update(gemini_updates).eq('url', beer['url']).execute()
            print(f"  💾 Persisted URL to gemini_data")
        except Exception as e:
            # Check if this is "column does not exist" error to fallback gracefully?
            # User said "done", so we assume column exists.
            print(f"  ⚠️ Error updating gemini_data (maybe column missing?): {e}")

    # 3. Update scraped_beers (Link)
    if scraped_updates:
        try:
            supabase.table('scraped_beers').update(scraped_updates).eq('url', beer['url']).execute()
            print(f"  🔗 Linked scraped_beer to Untappd URL")
            success = True
                
        except Exception as e:
            print(f"  ❌ Error updating scraped_beers: {e}")
            return None
            
    return untappd_payload or scraped_updates # Return truthy if we did something useful


async def enrich_untappd(limit: int = 50):
    """Enrich beers with Untappd data only. Loops until all processed."""
    print("=" * 70)
    print("🍺 Untappd Enrichment (Supabase: Normalized)")
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
        # We use the VIEW
        print(f"\n📂 Loading batch of beers from beer_info_view (Limit: {batch_size})...")
        response = supabase.table('beer_info_view') \
            .select('*') \
            .not_.is_('brewery_name_en', None) \
            .is_('untappd_rating', None) \
            .order('first_seen', desc=True) \
            .limit(batch_size) \
            .execute()
        
        # Also try beers with brewery_name_jp but no brewery_name_en logic? 
        # The view makes it simple. We prioritize those with Gemini data.
        
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
                total_untappd_found += 1
                if 'style' in updates:
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
    # The brewery manager logic is currently simplified/skipped in process_beer
    # If full brewery management is needed, this section would need to be re-evaluated
    # based on the new untappd_data table structure.
    # For now, we'll keep the manager initialization but remove the final update loop.
    # brewery_manager = BreweryManager() # Already initialized above
    
    # Get all beers with Untappd data to extract breweries
    # all_enriched = supabase.table('beers') \
    #     .select('untappd_brewery_name, brewery_name_en, brewery_name_jp') \
    #     .not_.is_('untappd_brewery_name', None) \
    #     .execute()
    
    # new_breweries = brewery_manager.extract_breweries_from_beers(all_enriched.data)
    # if new_breweries > 0:
    #     brewery_manager.save_breweries()
    #     print(f"  ✅ Added {new_breweries} new breweries")
    # else:
    #     print(f"  ℹ️  No new breweries to add")
    
    # stats = brewery_manager.get_stats()
    # print(f"  📊 Total breweries: {stats['total_breweries']}")
    
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

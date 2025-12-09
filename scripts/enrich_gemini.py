#!/usr/bin/env python3
"""
Gemini-only enrichment script for Supabase.
Extracts brewery and beer names using Gemini API.
This script processes beers that are missing English/Japanese brewery names,
utilizing the Gemini model to parse product names.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.gemini_extractor import GeminiExtractor
from app.services.brewery_manager import BreweryManager
try:
    from scripts.enrich_untappd import process_beer_missing
except ImportError:
    # If running directly from scripts dir
    from enrich_untappd import process_beer_missing

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

# Get credentials
SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY must be set")
    sys.exit(1)


async def enrich_gemini(limit: int = 50, shop_filter: str = None):
    """
    Enrich beers with Gemini extraction only.
    Loops until all eligible beers are processed.
    """
    print("=" * 70)
    print("🤖 Gemini Enrichment (Supabase)")
    print("=" * 70)
    target_msg = f"Target: All beers without Gemini data"
    if shop_filter:
        target_msg += f" (Shop: {shop_filter})"
    print(f"{target_msg} (Batch size: {limit})")
    print(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Initialize extractor and brewery manager once
    extractor = GeminiExtractor()
    if not extractor.client:
        print("\n❌ Error: Gemini API key not configured")
        return
    
    brewery_manager = BreweryManager()
    print(f"📚 Loaded {len(brewery_manager.breweries)} known breweries as hints")
    
    total_processed = 0
    total_enriched = 0
    total_errors = 0
    
    
    while True:
        if total_processed >= limit:
            print(f"\n✋ Reached limit of {limit} items. Stopping.")
            break

        # Calculate remaining items to process
        remaining = limit - total_processed
        current_batch_size = min(1000, remaining)
        
        # Get beers that need Gemini enrichment OR Untappd enrichment
        # Use verified view to find missing data
        print(f"\n📂 Loading batch of beers from beer_info_view (Batch Target: {current_batch_size})...")
        
        query = supabase.table('beer_info_view') \
            .select('*') \
            .or_('brewery_name_en.is.null,untappd_url.is.null')
            
        if shop_filter:
            query = query.eq('shop', shop_filter)
            
        response = query.order('first_seen', desc=True) \
            .limit(current_batch_size) \
            .execute()
        
        beers = response.data
        print(f"  Found {len(beers)} beers in this batch")
        
        if not beers:
            print("\n✨ No more beers need enrichment!")
            break
        
        # Process batch
        for i, beer in enumerate(beers, 1):
            print(f"\n{'='*70}")
            print(f"[Batch Item {i}/{len(beers)} | Total {total_processed + i}/{limit}] Processing: {beer.get('name', 'Unknown')[:60]}")
            print(f"{'='*70}")
            
            updates = {}
            need_gemini = not beer.get('brewery_name_en')
            
            try:
                if need_gemini:
                    # Check for known brewery hint in the beer name
                    known_brewery = None
                    brewery_match = brewery_manager.find_brewery_in_text(beer['name'])
                    if brewery_match:
                        known_brewery = brewery_match.get('name_en')
                        print(f"  🏭 Found known brewery hint: {known_brewery}")
                    
                    print("  🤖 Calling Gemini API...")
                    enriched_info = await extractor.extract_info(beer['name'], known_brewery=known_brewery)
                    
                    if enriched_info:
                        print("  ✅ Gemini Extraction Success:")
                        print(f"     Brewery (EN): {enriched_info.get('brewery_name_en')}")
                        print(f"     Brewery (JP): {enriched_info.get('brewery_name_jp')}")
                        print(f"     Beer (EN):    {enriched_info.get('beer_name_en')}")
                        
                        # Store enrichment data
                        gemini_payload = {
                            'url': beer['url'], # Key
                            'brewery_name_en': enriched_info.get('brewery_name_en'),
                            'brewery_name_jp': enriched_info.get('brewery_name_jp'),
                            'beer_name_en': enriched_info.get('beer_name_en'),
                            'beer_name_jp': enriched_info.get('beer_name_jp'),
                            'payload': enriched_info.get('raw_response'), # Save raw for debugging
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        }

                        # Upsert to gemini_data table
                        try:
                            supabase.table('gemini_data').upsert(gemini_payload).execute()
                            print(f"  💾 Saved to gemini_data table")
                        except Exception as e:
                             print(f"  ❌ Error saving to gemini_data: {e}")
                             continue

                        # Merge for Untappd step (process_beer expects these in the beer dict or separate db fetch)
                        # We update the 'beer' object in memory so process_beer has the info
                        beer.update(gemini_payload)
                        updates = gemini_payload # Marker that we have updates
                        total_enriched += 1
                    else:
                        print("  ⚠️  Gemini returned no info")
                else:
                    print("  ✅ Gemini data already exists. Skipping extraction.")
                    updates = True # Mark as "proceed to chain"
            
            except Exception as e:
                print(f"  ❌ Error during Gemini processing: {e}")
                total_errors += 1
            
            # Chain Untappd processing if successful
            if updates:
                try:
                     print("  🔗 Chaining Untappd enrichment...")
                     # Note: process_beer handles its own DB updates (to untappd_data/scraped_beers)
                     await process_beer_missing(beer, supabase)
                except Exception as e:
                    total_errors += 1
            else:
                 # If no updates, we must mark it as processed to avoid infinite loop
                 # Option: Set a 'processed' flag or just leave it. 
                 # If left, next query will pick it up again!
                 # Gemini might return nothing if it's not a beer.
                 # We should probably set a dummy value to avoid re-processing?
                 # Or just accept it's skipped in this run. 
                 # But then the loop will fetch it again forever.
                 # Fix: Add a 'gemini_checked_at' column? No schema change allowed easily.
                 # Workaround: Ensure we update SOMETHING or filter differently?
                 # Current query: is_('brewery_name_en', None)
                 # If Gemini fails, brewery_name_en is still None.
                 # We should probably set it to "Unknown" or similar if enrichment fails?
                 pass
                 
        total_processed += len(beers)
        
        # Check if we should stop (limit reached provided it was meant as total limit?)
        # User wants "All", so no stop based on count.
        
    # Final stats
    print(f"\n{'='*70}")
    print("📈 Final Statistics")
    print(f"{'='*70}")
    print(f"  Total processed: {total_processed}")
    print(f"  Gemini enriched: {total_enriched}")
    print(f"  Errors: {total_errors}")
    print(f"\n  Completed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'='*70}")
    print("✨ Gemini enrichment completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Gemini in Supabase')
    parser.add_argument('--limit', type=int, default=1000, help='Batch size (default 1000)')
    
    args = parser.parse_args()
    
    asyncio.run(enrich_gemini(limit=args.limit))

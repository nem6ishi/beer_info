#!/usr/bin/env python3
"""
Gemini-only enrichment script for Supabase
Extracts brewery and beer names using Gemini API
"""
import asyncio
import os
import sys
from datetime import datetime
from supabase import create_client, Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.gemini_extractor import GeminiExtractor
from app.services.brewery_manager import BreweryManager

# Get credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY must be set")
    sys.exit(1)


async def enrich_gemini(limit: int = 50):
    """Enrich beers with Gemini extraction only"""
    print("=" * 70)
    print("🤖 Gemini Enrichment (Supabase)")
    print("=" * 70)
    print(f"Target: First {limit} beers without Gemini data")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get beers that need Gemini enrichment
    print("\n📂 Loading beers from Supabase...")
    response = supabase.table('beers') \
        .select('*') \
        .is_('brewery_name_en', None) \
        .is_('brewery_name_jp', None) \
        .order('last_seen', desc=True) \
        .limit(limit) \
        .execute()
    
    beers = response.data
    print(f"  Found {len(beers)} beers needing Gemini enrichment")
    
    if not beers:
        print("\n✨ No beers need Gemini enrichment!")
        return
    
    # Initialize extractor and brewery manager
    extractor = GeminiExtractor()
    if not extractor.client:
        print("\n❌ Error: Gemini API key not configured")
        return
    
    brewery_manager = BreweryManager()
    print(f"📚 Loaded {len(brewery_manager.breweries)} known breweries as hints")
    
    # Process beers
    processed_count = 0
    gemini_enriched = 0
    errors = 0
    
    for i, beer in enumerate(beers, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(beers)}] Processing: {beer.get('name', 'Unknown')[:60]}")
        print(f"{'='*70}")
        
        updates = {}
        
        try:
            # Check for known brewery hint
            known_brewery = None
            brewery_match = brewery_manager.find_brewery_in_text(beer['name'])
            if brewery_match:
                known_brewery = brewery_match.get('name_en')
                print(f"  🏭 Found known brewery hint: {known_brewery}")
            
            print("  🤖 Calling Gemini API...")
            enriched_info = await extractor.extract_info(beer['name'], known_brewery=known_brewery)
            
            if enriched_info:
                if enriched_info.get('brewery_name_jp'):
                    updates['brewery_name_jp'] = enriched_info['brewery_name_jp']
                if enriched_info.get('brewery_name_en'):
                    updates['brewery_name_en'] = enriched_info['brewery_name_en']
                if enriched_info.get('beer_name_jp'):
                    updates['beer_name_jp'] = enriched_info['beer_name_jp']
                if enriched_info.get('beer_name_en'):
                    updates['beer_name_en'] = enriched_info['beer_name_en']
                
                print(f"  ✅ Extracted:")
                print(f"     Brewery: {updates.get('brewery_name_en', 'N/A')} / {updates.get('brewery_name_jp', 'N/A')}")
                print(f"     Beer: {updates.get('beer_name_en', 'N/A')} / {updates.get('beer_name_jp', 'N/A')}")
                gemini_enriched += 1
            else:
                print(f"  ⚠️  Gemini returned no data")
        
        except Exception as e:
            print(f"  ❌ Gemini error: {e}")
            errors += 1
        
        # Update database
        if updates:
            try:
                supabase.table('beers').update(updates).eq('id', beer['id']).execute()
                print(f"  💾 Updated database")
                processed_count += 1
            except Exception as e:
                print(f"  ❌ Database update error: {e}")
                errors += 1
        
        # Progress checkpoint every 10
        if i % 10 == 0:
            print(f"\n💾 Checkpoint: Processed {i}/{len(beers)} beers")
    
    # Final stats
    print(f"\n{'='*70}")
    print("📈 Final Statistics")
    print(f"{'='*70}")
    print(f"  Beers processed: {processed_count}/{len(beers)}")
    print(f"  Gemini enriched: {gemini_enriched}")
    print(f"  Errors: {errors}")
    print(f"\n  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'='*70}")
    print("✨ Gemini enrichment completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Gemini in Supabase')
    parser.add_argument('--limit', type=int, default=50, help='Number of beers to process')
    
    args = parser.parse_args()
    
    asyncio.run(enrich_gemini(limit=args.limit))

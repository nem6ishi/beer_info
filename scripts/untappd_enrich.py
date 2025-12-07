#!/usr/bin/env python3
"""
Untappd-only enrichment that reads/writes from Supabase
Searches and scrapes Untappd data for beers that already have Gemini data
"""
import asyncio
import os
import sys
from datetime import datetime
from supabase import create_client, Client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import get_untappd_url, scrape_beer_details

# Get credentials
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)


async def untappd_enrich(limit: int = 30):
    """Enrich beers with Untappd data (requires existing Gemini data)"""
    print("=" * 70)
    print("🍺 Untappd Enrichment (Supabase)")
    print("=" * 70)
    print(f"Target: First {limit} beers with Gemini data but no Untappd URL")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Get beers that have Gemini data but no Untappd URL
    print("\n📂 Loading beers from Supabase...")
    response = supabase.table('beers') \
        .select('*') \
        .is_('untappd_url', None) \
        .not_.is_('brewery_name_en', None) \
        .order('last_seen', desc=True) \
        .limit(limit) \
        .execute()
    
    beers = response.data
    print(f"  Found {len(beers)} beers needing Untappd enrichment")
    
    if not beers:
        print("\n✨ No beers need Untappd enrichment!")
        return
    
    # Process beers
    processed_count = 0
    enriched_count = 0
    
    for i, beer in enumerate(beers, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(beers)}] Processing: {beer.get('name', 'Unknown')[:60]}")
        print(f"{'='*70}")
        
        updates = {}
        
        # Untappd enrichment
        try:
            brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
            beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
            
            if not brewery and not beer_name:
                print("  ⚠️  No brewery/beer name available, skipping")
                continue
            
            print(f"🍺 Searching Untappd for: {brewery} - {beer_name}")
            untappd_url = get_untappd_url(brewery, beer_name)
            
            if untappd_url:
                updates['untappd_url'] = untappd_url
                print(f"  ✅ Found: {untappd_url}")
                
                # Scrape details if it's a direct beer page
                if "untappd.com/b/" in untappd_url:
                    await asyncio.sleep(2)
                    print(f"  🔄 Scraping details...")
                    details = scrape_beer_details(untappd_url)
                    if details:
                        updates.update(details)
                        updates['untappd_fetched_at'] = datetime.now().isoformat()
                        print(f"  ✅ Details scraped")
                        enriched_count += 1
            else:
                print(f"  ❌ Untappd URL not found")
            
            await asyncio.sleep(1)
        except Exception as e:
            print(f"  ❌ Untappd error: {e}")
        
        # Update database
        if updates:
            try:
                supabase.table('beers').update(updates).eq('id', beer['id']).execute()
                print(f"  💾 Updated database")
                processed_count += 1
            except Exception as e:
                print(f"  ❌ Database update error: {e}")
        
        # Progress save every 10
        if i % 10 == 0:
            print(f"\n💾 Checkpoint: Processed {i}/{len(beers)} beers")
    
    # Final stats
    print(f"\n{'='*70}")
    print("📈 Final Statistics")
    print(f"{'='*70}")
    print(f"  Beers processed: {processed_count}/{len(beers)}")
    print(f"  Untappd enriched: {enriched_count}")
    print(f"\n  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'='*70}")
    print("✨ Untappd enrichment completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Untappd')
    parser.add_argument('--limit', type=int, default=30, help='Number of beers to process')
    
    args = parser.parse_args()
    
    asyncio.run(untappd_enrich(limit=args.limit))

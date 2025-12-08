#!/usr/bin/env python3
"""
Untappd-only enrichment script for Supabase
Enriches beers that already have Gemini data but missing Untappd info
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


async def enrich_untappd(limit: int = 50):
    """Enrich beers with Untappd data only"""
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
        .not_.is_('brewery_name_en', None) \
        .is_('untappd_url', None) \
        .order('last_seen', desc=True) \
        .limit(limit) \
        .execute()
    
    # Also try beers with brewery_name_jp but no brewery_name_en
    if len(response.data) < limit:
        response2 = supabase.table('beers') \
            .select('*') \
            .not_.is_('brewery_name_jp', None) \
            .is_('untappd_url', None) \
            .order('last_seen', desc=True) \
            .limit(limit - len(response.data)) \
            .execute()
        
        # Merge results, avoiding duplicates
        existing_ids = {b['id'] for b in response.data}
        for beer in response2.data:
            if beer['id'] not in existing_ids:
                response.data.append(beer)
    
    beers = response.data
    print(f"  Found {len(beers)} beers needing Untappd enrichment")
    
    if not beers:
        print("\n✨ No beers need Untappd enrichment!")
        return
    
    # Process beers
    processed_count = 0
    untappd_found = 0
    details_scraped = 0
    errors = 0
    
    for i, beer in enumerate(beers, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(beers)}] Processing: {beer.get('name', 'Unknown')[:60]}")
        print(f"{'='*70}")
        
        # Extract brewery and beer names
        brewery = beer.get('brewery_name_en') or beer.get('brewery_name_jp')
        beer_name = beer.get('beer_name_en') or beer.get('beer_name_jp')
        
        if not brewery or not beer_name:
            print(f"  ⚠️  Missing brewery or beer name - skipping")
            continue
        
        updates = {}
        
        try:
            print(f"  🔍 Searching Untappd for: {brewery} - {beer_name}")
            untappd_url = get_untappd_url(brewery, beer_name)
            
            if untappd_url:
                updates['untappd_url'] = untappd_url
                print(f"  ✅ Found URL: {untappd_url}")
                untappd_found += 1
                
                # If it's a direct beer page, scrape details
                if "untappd.com/b/" in untappd_url:
                    await asyncio.sleep(2)  # Rate limiting
                    print(f"  🔄 Scraping beer details...")
                    
                    try:
                        details = scrape_beer_details(untappd_url)
                        if details:
                            updates.update(details)
                            updates['untappd_fetched_at'] = datetime.now().isoformat()
                            print(f"  ✅ Details scraped:")
                            print(f"     Style: {details.get('untappd_style', 'N/A')}")
                            print(f"     ABV: {details.get('untappd_abv', 'N/A')}, IBU: {details.get('untappd_ibu', 'N/A')}")
                            print(f"     Rating: {details.get('untappd_rating', 'N/A')} ({details.get('untappd_rating_count', 'N/A')})")
                            details_scraped += 1
                        else:
                            print(f"  ⚠️  Could not scrape details from page")
                    except Exception as detail_error:
                        print(f"  ⚠️  Error scraping details: {detail_error}")
            else:
                print(f"  ❌ Untappd URL not found")
            
            await asyncio.sleep(1)  # Rate limiting between searches
        
        except Exception as e:
            print(f"  ❌ Untappd search error: {e}")
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
    print(f"  Untappd URLs found: {untappd_found}")
    print(f"  Details scraped: {details_scraped}")
    print(f"  Errors: {errors}")
    print(f"\n  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'='*70}")
    print("✨ Untappd enrichment completed!")
    print(f"{'='*70}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Untappd in Supabase')
    parser.add_argument('--limit', type=int, default=50, help='Number of beers to process')
    
    args = parser.parse_args()
    
    asyncio.run(enrich_untappd(limit=args.limit))

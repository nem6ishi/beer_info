#!/usr/bin/env python3
"""
Build initial brewery database from existing beers.json
Extracts all Untappd brewery names and creates breweries.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from app.services.brewery_manager import BreweryManager

def main():
    print("=" * 60)
    print("🏭 Building Brewery Database")
    print("=" * 60)
    
    # Load beers
    beers_path = "data/beers.json"
    if not os.path.exists(beers_path):
        print(f"❌ Error: {beers_path} not found")
        return
    
    with open(beers_path, 'r', encoding='utf-8') as f:
        beers = json.load(f)
    
    print(f"📂 Loaded {len(beers)} beers from {beers_path}")
    
    # Count beers with Untappd data
    with_untappd = sum(1 for b in beers if b.get('untappd_brewery_name'))
    print(f"📊 Beers with Untappd data: {with_untappd}")
    
    # Initialize brewery manager
    manager = BreweryManager()
    
    # Extract breweries
    print("\n🔍 Extracting breweries from Untappd data...")
    new_count = manager.extract_breweries_from_beers(beers)
    
    # Get stats
    stats = manager.get_brewery_stats()
    
    print(f"\n✅ Extraction complete!")
    print(f"  🆕 New breweries added: {new_count}")
    print(f"  📦 Total breweries: {stats['total_breweries']}")
    print(f"  🇯🇵 With Japanese names: {stats['with_japanese_names']}")
    print(f"  🍺 Total beers tracked: {stats['total_beers_tracked']}")
    print(f"  📈 Avg beers per brewery: {stats['avg_beers_per_brewery']:.1f}")
    
    # Save brewery database
    manager.save_breweries()
    
    # Show top breweries
    print("\n🏆 Top 10 Breweries by Beer Count:")
    sorted_breweries = sorted(
        manager.breweries, 
        key=lambda b: b.get('beer_count', 0), 
        reverse=True
    )[:10]
    
    for i, brewery in enumerate(sorted_breweries, 1):
        name = brewery.get('name_en', 'Unknown')
        count = brewery.get('beer_count', 0)
        jp_name = brewery.get('name_jp', '')
        jp_suffix = f" ({jp_name})" if jp_name else ""
        print(f"  {i:2d}. {name}{jp_suffix}: {count} beers")
    
    print("\n" + "=" * 60)
    print("✨ Brewery database built successfully!")
    print(f"📁 Saved to: data/breweries.json")
    print("=" * 60)

if __name__ == "__main__":
    main()

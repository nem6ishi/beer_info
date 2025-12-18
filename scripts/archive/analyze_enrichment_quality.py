
import asyncio
import os
import sys
import logging
from supabase import create_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.utils.script_utils import setup_script

# Setup
supabase, logger = setup_script("analyze_quality")

async def analyze():
    print("📊 Analyzing Enrichment Quality...")
    
    # Fetch random sample of successfully linked beers
    # We want beers that have a specific Untappd URL (not a search link)
    res = supabase.table('beer_info_view').select('*') \
        .not_.is_('untappd_url', 'null') \
        .ilike('untappd_url', '%/b/%') \
        .limit(50) \
        .execute()
        
    beers = res.data
    print(f"Loaded {len(beers)} samples.")
    
    # We also need the ACTUAL Untappd data to compare names
    # beer_info_view has scraped name and Gemini extracted names (beer_name_en, brewery_name_en)
    # We need to fetch untappd_data to get the "ground truth" names
    
    print("\n{:<60} | {:<30} | {:<30} | {:<10}".format("Original Name", "Gemini Extraction", "Untappd Match", "Status"))
    print("-" * 140)
    
    for beer in beers:
        original_name = beer.get('name', '')[:58]
        gemini_beer = beer.get('beer_name_en', '') or ''
        gemini_brewery = beer.get('brewery_name_en', '') or ''
        gemini_str = f"{gemini_brewery} / {gemini_beer}"[:28]
        
        url = beer.get('untappd_url')
        
        # Fetch untappd data
        u_res = supabase.table('untappd_data').select('*').eq('untappd_url', url).execute()
        if u_res.data:
            u_data = u_res.data[0]
            u_beer = u_data.get('untappd_beer_name', '')
            u_brewery = u_data.get('untappd_brewery_name', '')
            match_str = f"{u_brewery} / {u_beer}"[:28]
            
            # Simple heuristic score
            status = "✅"
            if gemini_beer.lower() not in u_beer.lower() and u_beer.lower() not in gemini_beer.lower():
                status = "⚠️ Name"
            if gemini_brewery and gemini_brewery.lower() not in u_brewery.lower() and u_brewery.lower() not in gemini_brewery.lower():
                 status = "⚠️ Brew"
                 
            print("{:<60} | {:<30} | {:<30} | {}".format(original_name, gemini_str, match_str, status))

if __name__ == "__main__":
    asyncio.run(analyze())

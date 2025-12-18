#!/usr/bin/env python3
"""
SHIM for backward compatibility.
Logic moved to app/commands/enrich_untappd.py
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.commands.enrich_untappd import process_beer_missing as _process_new, process_beer_refresh as _process_refresh_new, enrich_untappd as _enrich_main

# Adapter for old signature: process_beer_missing(beer, supabase, offline=False)
async def process_beer_missing(beer, supabase, offline=False):
    return await _process_new(beer, offline=offline)

# Adapter for old signature: process_beer_refresh(beer, supabase)
async def process_beer_refresh(beer, supabase):
    return await _process_refresh_new(beer)

# Main entry point adapter
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--mode', choices=['missing', 'refresh'], default='missing')
    parser.add_argument('--shop_filter', type=str, default=None)
    parser.add_argument('--name_filter', type=str, default=None)
    
    args = parser.parse_args()
    
    # Run new command
    from app.commands.enrich_breweries import enrich_breweries
    
    collected = asyncio.run(_enrich_main(limit=args.limit, mode=args.mode, shop_filter=args.shop_filter, name_filter=args.name_filter))
    
    if collected:
         print(f"\nFound {len(collected)} breweries to potentially enrich. Starting brewery enrichment...")
         asyncio.run(enrich_breweries(target_urls=list(collected)))

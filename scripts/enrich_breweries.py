#!/usr/bin/env python3
"""
SHIM for backward compatibility.
Logic moved to app/commands/enrich_breweries.py
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.commands.enrich_breweries import enrich_breweries as _enrich_main

if __name__ == "__main__":
    import argparse
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--limit', type=int, default=50)
    arg_parser.add_argument('--force', action='store_true', help="Force update even if fresh")
    arg_parser.add_argument('--targets', nargs='+', help="List of specific Untappd URLs to enrich")
    args = arg_parser.parse_args()
    
    asyncio.run(_enrich_main(limit=args.limit, force=args.force, target_urls=args.targets))

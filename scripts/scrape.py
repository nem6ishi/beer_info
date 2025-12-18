#!/usr/bin/env python3
"""
SHIM for backward compatibility.
Logic moved to app/commands/scrape.py
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.commands.scrape import scrape_to_supabase

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape beer data to Supabase')
    parser.add_argument('--limit', type=int, help='Limit items per scraper')
    parser.add_argument('--new', action='store_true', help='New items only scrape')
    parser.add_argument('--full', action='store_true', help='Full scrape (ignore sold-out threshold)')
    parser.add_argument('--reset-dates', action='store_true', help='Reset first_seen timestamps')
    
    args = parser.parse_args()
    
    asyncio.run(scrape_to_supabase(limit=args.limit, new_only=args.new, full_scrape=args.full, reset_first_seen=args.reset_dates))

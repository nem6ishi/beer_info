#!/usr/bin/env python3
"""
SHIM for backward compatibility.
Logic moved to app/commands/enrich_gemini.py
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.commands.enrich_gemini import enrich_gemini as _enrich_main

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich beer data with Gemini in Supabase')
    parser.add_argument('--limit', type=int, default=1000, help='Batch size (default 1000)')
    parser.add_argument('--offline', action='store_true', help='Offline mode')
    parser.add_argument('--shop', type=str, help='Filter by shop name')
    parser.add_argument('--keyword', type=str, help='Filter by product name keyword')
    parser.add_argument('--force', action='store_true', help='Force re-process')
    
    args = parser.parse_args()
    
    asyncio.run(_enrich_main(limit=args.limit, offline=args.offline, shop_filter=args.shop, keyword_filter=args.keyword, force_reprocess=args.force))

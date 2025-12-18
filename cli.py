#!/usr/bin/env python3
import asyncio
import argparse
import sys
import logging

from app.core.logging import setup_logging
from app.commands.scrape import scrape_to_supabase
from app.commands.enrich_untappd import enrich_untappd
from app.commands.enrich_gemini import enrich_gemini
from app.commands.enrich_breweries import enrich_breweries

# Setup global logging
logger = setup_logging("cli")

async def run_scrape(args):
    await scrape_to_supabase(
        limit=args.limit,
        new_only=args.new,
        full_scrape=args.full,
        reset_first_seen=args.reset_dates
    )

async def run_enrich_untappd(args):
    collected_urls = await enrich_untappd(
        limit=args.limit,
        mode=args.mode,
        shop_filter=args.shop,
        name_filter=args.keyword
    )
    
    # Chain brewery enrichment if URLs were collected
    if collected_urls:
        logger.info(f"\n🔗 Chaining Brewery Enrichment: Found {len(collected_urls)} URLs")
        await enrich_breweries(target_urls=list(collected_urls))

async def run_enrich_gemini(args):
    await enrich_gemini(
        limit=args.limit,
        shop_filter=args.shop,
        keyword_filter=args.keyword,
        offline=args.offline,
        force_reprocess=args.force
    )

async def run_enrich_breweries(args):
    await enrich_breweries(
        limit=args.limit,
        force=args.force,
        target_urls=args.targets
    )

def main():
    parser = argparse.ArgumentParser(description="Beer Info CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # === SCRAPE ===
    scrape_parser = subparsers.add_parser("scrape", help="Scrape beer sites")
    scrape_parser.add_argument("--limit", type=int, help="Limit items per scraper")
    scrape_parser.add_argument("--new", action="store_true", help="New items only")
    scrape_parser.add_argument("--full", action="store_true", help="Full scrape (ignore sold-out threshold)")
    scrape_parser.add_argument("--reset-dates", action="store_true", help="Reset first_seen timestamps")
    
    # === ENRICH ===
    enrich_parser = subparsers.add_parser("enrich", help="Enrichment commands")
    enrich_subparsers = enrich_parser.add_subparsers(dest="enrich_command", help="Enrichment type")
    
    # enrich untappd
    untappd = enrich_subparsers.add_parser("untappd", help="Enrich with Untappd data")
    untappd.add_argument("--limit", type=int, default=50, help="Batch size")
    untappd.add_argument("--mode", choices=["missing", "refresh"], default="missing", help="Enrichment mode")
    untappd.add_argument("--shop", type=str, help="Filter by shop name")
    untappd.add_argument("--keyword", type=str, help="Filter by beer name")
    
    # enrich gemini
    gemini = enrich_subparsers.add_parser("gemini", help="Enrich with Gemini AI")
    gemini.add_argument("--limit", type=int, default=50, help="Batch size")
    gemini.add_argument("--offline", action="store_true", help="Offline mode (verify only)")
    gemini.add_argument("--shop", type=str, help="Filter by shop name")
    gemini.add_argument("--keyword", type=str, help="Filter by product name")
    gemini.add_argument("--force", action="store_true", help="Force re-process")
    
    # enrich breweries
    breweries = enrich_subparsers.add_parser("breweries", help="Enrich brewery details")
    breweries.add_argument("--limit", type=int, default=50, help="Batch size")
    breweries.add_argument("--force", action="store_true", help="Force update")
    breweries.add_argument("--targets", nargs="+", help="Specific Untappd URLs")

    args = parser.parse_args()
    
    if args.command == "scrape":
        asyncio.run(run_scrape(args))
    elif args.command == "enrich":
        if args.enrich_command == "untappd":
            asyncio.run(run_enrich_untappd(args))
        elif args.enrich_command == "gemini":
            asyncio.run(run_enrich_gemini(args))
        elif args.enrich_command == "breweries":
            asyncio.run(run_enrich_breweries(args))
        else:
            enrich_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

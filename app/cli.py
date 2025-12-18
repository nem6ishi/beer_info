import asyncio
import argparse
import sys
import os
import logging

from app.core.logging import setup_logging

# Setup global logging
logger = setup_logging("cli")

def main():
    parser = argparse.ArgumentParser(description="Beer Info CLI (Supabase Operations)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers and save to Supabase")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of items to scrape", default=None)
    scrape_parser.add_argument("--new", action="store_true", help="Scrape new items only (stop after 30 existing)")
    scrape_parser.add_argument("--full", action="store_true", help="Full scrape (ignore sold-out threshold)")
    scrape_parser.add_argument("--reset-dates", action="store_true", help="Reset first_seen timestamps")

    # Combined Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Run full enrichment pipeline (Gemini -> Untappd -> Breweries)")
    enrich_parser.add_argument("--limit", type=int, help="Limit number of items to enrich per step", default=50)
    enrich_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    enrich_parser.add_argument("--keyword", type=str, help="Filter enrichment by partial name match", default=None)

    # Enrich Gemini only
    enrich_gemini_parser = subparsers.add_parser("enrich-gemini", help="Run Gemini enrichment only")
    enrich_gemini_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    enrich_gemini_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    enrich_gemini_parser.add_argument("--keyword", type=str, help="Filter enrichment by partial name match", default=None)
    # Added missing args from shim/workflow usage
    enrich_gemini_parser.add_argument("--offline", action="store_true", help="Offline mode")
    enrich_gemini_parser.add_argument("--force", action="store_true", help="Force re-process")

    
    # Enrich Untappd only
    enrich_untappd_parser = subparsers.add_parser("enrich-untappd", help="Run Untappd enrichment only")
    enrich_untappd_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    enrich_untappd_parser.add_argument("--mode", choices=['missing', 'refresh'], default='missing', help="Enrichment mode")
    enrich_untappd_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    enrich_untappd_parser.add_argument("--name_filter", type=str, help="Filter enrichment by partial name match", default=None)

    # Enrich Breweries only
    enrich_breweries_parser = subparsers.add_parser("enrich-breweries", help="Run Brewery enrichment only")
    enrich_breweries_parser.add_argument("--limit", type=int, default=50)
    enrich_breweries_parser.add_argument("--force", action='store_true')
    enrich_breweries_parser.add_argument("--targets", nargs='+', help="Specific Untappd URLs")

    # Update stock command
    update_stock_parser = subparsers.add_parser("update-stock", help="Check and update stock status for existing items")
    update_stock_parser.add_argument("--limit", type=int, default=None, help="Limit number of items to check")
    update_stock_parser.add_argument("--shop", type=str, help="Filter by shop name", default=None)
    update_stock_parser.add_argument("--sort-rating", action="store_true", help="Sort by Untappd Rating (DESC)")

    # Sync command
    subparsers.add_parser("sync", help="Download Supabase data to local JSON")

    # Clear command
    subparsers.add_parser("clear", help="Clear all data from the database")

    args = parser.parse_args()

    if args.command == "scrape":
        from app.commands.scrape import scrape_to_supabase
        asyncio.run(scrape_to_supabase(limit=args.limit, new_only=args.new, full_scrape=args.full, reset_first_seen=args.reset_dates))
    
    elif args.command == "update-stock":
        from app.commands.update_stock import update_stock_status
        asyncio.run(update_stock_status(limit=args.limit, shop_filter=args.shop, sort_rating=args.sort_rating))

    elif args.command == "enrich":
        # Import commands
        from app.commands.enrich_gemini import enrich_gemini
        from app.commands.enrich_untappd import enrich_untappd
        from app.commands.enrich_breweries import enrich_breweries

        async def run_pipeline():
            logger.info("🚀 Starting Full Enrichment Pipeline...")
            
            logger.info("\n--- Step 1: Gemini Enrichment ---")
            await enrich_gemini(limit=args.limit, shop_filter=args.shop, keyword_filter=args.keyword)
            
            logger.info("\n--- Step 2: Untappd Enrichment ---")
            found_brewery_urls = await enrich_untappd(limit=args.limit, mode='missing', shop_filter=args.shop, name_filter=args.keyword)
            
            if found_brewery_urls:
                logger.info(f"\n--- Step 3: Brewery Enrichment (Targeting {len(found_brewery_urls)} breweries) ---")
                await enrich_breweries(limit=args.limit, target_urls=list(found_brewery_urls))
            else:
                logger.info("\n--- Step 3: Brewery Enrichment (Skipped) ---")
                logger.info("ℹ️  No new brewery URLs found to enrich.")

        asyncio.run(run_pipeline())
        
    elif args.command == "enrich-gemini":
        from app.commands.enrich_gemini import enrich_gemini
        asyncio.run(enrich_gemini(limit=args.limit, shop_filter=args.shop, keyword_filter=args.keyword, offline=args.offline, force_reprocess=args.force))
        
    elif args.command == "enrich-untappd":
        from app.commands.enrich_untappd import enrich_untappd
        asyncio.run(enrich_untappd(limit=args.limit, mode=args.mode, shop_filter=args.shop, name_filter=args.name_filter))
    
    elif args.command == "enrich-breweries":
        from app.commands.enrich_breweries import enrich_breweries
        asyncio.run(enrich_breweries(limit=args.limit, force=args.force, target_urls=args.targets))
        
    elif args.command == "sync":
        # Legacy script support - assuming these still live in scripts or haven't been moved yet.
        # If they haven't been refactored, we can keep using scripts. 
        # But import logic might need adjustment if scripts assumes running from root.
        # Providing basic support or error if not refactored.
        try:
            from scripts.sync_local import sync_from_supabase
            sync_from_supabase()
        except ImportError:
            logger.error("Sync script not found or not refactored.")
            
    elif args.command == "clear":
        try:
            from scripts.clear_db import clear_database
            clear_database()
        except ImportError:
             logger.error("Clear DB script not found or not refactored.")
             
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

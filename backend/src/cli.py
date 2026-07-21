"""
Main CLI Entry Point for Craft Beer Alert Japan.

This script provides various commands to manage the data pipeline:
- scrape: Fetch latest beer data from e-commerce sites.
- enrich-extract: Use LLMs (Gemini/MLX) to extract brewery and beer names in English.
- enrich-untappd: Search Untappd based on the extracted English names.
- enrich-breweries: Update brewery information (location, type, etc.) from Untappd.
- clean: Safely remove corrupted data from the database.
- ...and more.
"""
import asyncio
import argparse
import sys
import logging
from typing import Optional, Set

from .core.logging import setup_logging

# Setup global logging
logger: logging.Logger = setup_logging("cli")

def main() -> None:
    parser = argparse.ArgumentParser(description="Beer Info CLI (Supabase Operations)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers and save to Supabase")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of items to scrape", default=None)
    scrape_parser.add_argument("--new", action="store_true", help="Scrape new items only (stop after 30 existing)")
    scrape_parser.add_argument("--full", action="store_true", help="Full scrape (ignore sold-out threshold)")
    scrape_parser.add_argument("--reset-dates", action="store_true", help="Reset first_seen timestamps")

    # Combined Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Run full enrichment pipeline")
    enrich_parser.add_argument("--limit", type=int, help="Limit number of items to enrich per step", default=50)
    enrich_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    enrich_parser.add_argument("--keyword", type=str, help="Filter enrichment by partial name match", default=None)
    enrich_parser.add_argument("--llm", type=str, choices=["gemini", "local_mlx"], default="gemini", help="LLM provider to use")
    enrich_parser.add_argument("--llm-model", type=str, default=None, help="Specific LLM model ID to use")

    # Enrich Extract only (Phase 1 of Enrichment)
    # Uses LLMs to parse Japanese/English raw names and extract structured data
    enrich_extract_parser = subparsers.add_parser("enrich-extract", help="Run LLM extraction to get structured English names")
    enrich_extract_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    enrich_extract_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    enrich_extract_parser.add_argument("--keyword", type=str, help="Filter enrichment by partial name match", default=None)
    enrich_extract_parser.add_argument("--llm", type=str, choices=["gemini", "local_mlx"], default="gemini", help="LLM provider to use")
    enrich_extract_parser.add_argument("--llm-model", type=str, default=None, help="Specific LLM model ID to use")
    enrich_extract_parser.add_argument("--offline", action="store_true", help="Offline mode")
    enrich_extract_parser.add_argument("--force", action="store_true", help="Force re-process")
    enrich_extract_parser.add_argument("--retry-unlinked", action="store_true", help="Force re-process only for items with missing untappd_url")

    # Enrich Untappd only (Phase 2 of Enrichment)
    # Uses the extracted English names to search Untappd and link IDs
    enrich_untappd_parser = subparsers.add_parser("enrich-untappd", help="Search Untappd using extracted English names")
    enrich_untappd_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    enrich_untappd_parser.add_argument("--mode", choices=['missing', 'refresh', 'retry-failures'], default='missing', help="Enrichment mode")
    enrich_untappd_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    enrich_untappd_parser.add_argument("--name_filter", type=str, help="Filter enrichment by partial name match", default=None)
    enrich_untappd_parser.add_argument("--llm", type=str, choices=["gemini", "local_mlx"], default="gemini", help="LLM provider for retry inference")
    enrich_untappd_parser.add_argument("--llm-model", type=str, default=None, help="Specific LLM model ID to use")
    enrich_untappd_parser.add_argument("--force", action="store_true", help="Force re-process / ignore backoff")

    # Enrich Breweries only
    enrich_breweries_parser = subparsers.add_parser("enrich-breweries", help="Run Brewery enrichment only")
    enrich_breweries_parser.add_argument("--limit", type=int, default=50)
    enrich_breweries_parser.add_argument("--force", action='store_true')
    enrich_breweries_parser.add_argument("--targets", nargs='+', help="Specific Untappd URLs")

    # Update stock command
    update_stock_parser = subparsers.add_parser("update-stock", help="Check and update stock status")
    update_stock_parser.add_argument("--limit", type=int, default=None, help="Limit number of items to check")
    update_stock_parser.add_argument("--shop", type=str, help="Filter by shop name", default=None)
    update_stock_parser.add_argument("--sort-rating", action="store_true", help="Sort by Untappd Rating (DESC)")

    # Sync command
    subparsers.add_parser("sync", help="Download Supabase data to local JSON")

    # Check variants command
    check_variants_parser = subparsers.add_parser("check-variants", help="Check for variant mismatches in beer data")
    check_variants_parser.add_argument("--clear", action="store_true", help="Automatically clear mismatched untappd_urls")

    # Clear command
    subparsers.add_parser("clear", help="Clear all data from the database")

    # Clean command
    clean_parser = subparsers.add_parser("clean", help="Safely delete corrupted records")
    clean_parser.add_argument("--table", type=str, required=True, help="Table name to clean from")
    clean_parser.add_argument("--column", type=str, required=True, help="Column name to match")
    clean_parser.add_argument("--pattern", type=str, required=True, help="LIKE pattern to match")
    clean_parser.add_argument("--execute", action="store_true", help="Actually execute the deletion (defaults to dry-run)")

    args: argparse.Namespace = parser.parse_args()

    if args.command == "scrape":
        from .commands.scrape import scrape_to_supabase
        asyncio.run(scrape_to_supabase(limit=args.limit, new_only=args.new, full_scrape=args.full, reset_first_seen=args.reset_dates))
    
    elif args.command == "update-stock":
        from .commands.update_stock import update_stock_status
        asyncio.run(update_stock_status(limit=args.limit, shop_filter=args.shop, sort_rating=args.sort_rating))

    elif args.command == "enrich":
        from .commands.enrich_extract import enrich_extract
        from .commands.enrich_untappd import enrich_untappd
        from .commands.enrich_breweries import enrich_breweries

        async def run_pipeline() -> None:
            logger.info("🚀 Starting Full Enrichment Pipeline...")
            
            logger.info(f"\n--- Step 1: LLM Extraction ({args.llm}) ---")
            await enrich_extract(limit=args.limit, shop_filter=args.shop, keyword_filter=args.keyword, llm_provider=args.llm, llm_model_id=args.llm_model)
            
            logger.info("\n--- Step 2: Untappd Enrichment ---")
            found_brewery_urls: Optional[Set[str]] = await enrich_untappd(limit=args.limit, mode='missing', shop_filter=args.shop, name_filter=args.keyword, llm_provider=args.llm, llm_model_id=args.llm_model)
            
            if found_brewery_urls:
                logger.info(f"\n--- Step 3: Brewery Enrichment (Targeting {len(found_brewery_urls)} breweries) ---")
                await enrich_breweries(limit=args.limit, target_urls=list(found_brewery_urls))
            else:
                logger.info("\n--- Step 3: Brewery Enrichment (Skipped) ---")
                logger.info("ℹ️  No new brewery URLs found to enrich.")

        asyncio.run(run_pipeline())
        
    elif args.command == "enrich-extract":
        from .commands.enrich_extract import enrich_extract
        asyncio.run(enrich_extract(limit=args.limit, shop_filter=args.shop, keyword_filter=args.keyword, offline=args.offline, force_reprocess=args.force, retry_unlinked=getattr(args, 'retry_unlinked', False), llm_provider=args.llm, llm_model_id=args.llm_model))
        
    elif args.command == "enrich-untappd":
        from .commands.enrich_untappd import enrich_untappd
        asyncio.run(enrich_untappd(limit=args.limit, mode=args.mode, shop_filter=args.shop, name_filter=args.name_filter, force=args.force, llm_provider=args.llm, llm_model_id=args.llm_model))
    
    elif args.command == "enrich-breweries":
        from .commands.enrich_breweries import enrich_breweries
        asyncio.run(enrich_breweries(limit=args.limit, force=args.force, target_urls=args.targets))
        
    elif args.command == "sync":
        try:
            from ..scripts.sync_local import sync_from_supabase
            sync_from_supabase()
        except ImportError:
            logger.error("Sync script not found.")
            
    elif args.command == "clean":
        from .commands.clean_data import clean_data
        asyncio.run(clean_data(table=args.table, column=args.column, pattern=args.pattern, dry_run=not args.execute))
            
    elif args.command == "check-variants":
        from .commands.check_variants import check_variants
        asyncio.run(check_variants(auto_clear=args.clear))
            
    elif args.command == "clear":
        try:
            from ..scripts.clear_db import clear_database
            clear_database()
        except ImportError:
             logger.error("Clear DB script not found.")
             
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

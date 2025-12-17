import asyncio
import argparse
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

def main():
    parser = argparse.ArgumentParser(description="Beer Info CLI (Supabase Operations)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers and save to Supabase")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of items to scrape", default=None)
    # Reverse argument removed
    # Reverse argument removed
    scrape_parser.add_argument("--new", action="store_true", help="新商品スクレイプ: 既存商品が30件続いたら停止")
    scrape_parser.add_argument("--full", action="store_true", help="全件スクレイプ: 停止リミットを無視して全件取得")
    scrape_parser.add_argument("--reset-dates", action="store_true", help="Reset first_seen timestamps")
    # Combined Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Run full enrichment pipeline (Gemini -> Untappd -> Breweries)")
    enrich_parser.add_argument("--limit", type=int, help="Limit number of items to enrich per step", default=50)
    enrich_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)

    # Enrich Gemini only
    enrich_gemini_parser = subparsers.add_parser("enrich-gemini", help="Run Gemini enrichment only")
    enrich_gemini_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    enrich_gemini_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)
    
    # Enrich Untappd only
    enrich_untappd_parser = subparsers.add_parser("enrich-untappd", help="Run Untappd enrichment only")
    enrich_untappd_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    enrich_untappd_parser.add_argument("--mode", choices=['missing', 'refresh'], default='missing', help="Enrichment mode: 'missing' for new items, 'refresh' for existing items")
    enrich_untappd_parser.add_argument("--shop", type=str, help="Filter enrichment by shop name", default=None)

    # Sync command
    subparsers.add_parser("sync", help="Download Supabase data to local JSON")

    # Clear command
    subparsers.add_parser("clear", help="Clear all data from the database")

    args = parser.parse_args()

    if args.command == "scrape":
        from scripts.scrape import scrape_to_supabase
        asyncio.run(scrape_to_supabase(limit=args.limit, new_only=args.new, full_scrape=args.full, reset_first_seen=args.reset_dates))
    elif args.command == "enrich":
        from scripts.enrich_gemini import enrich_gemini
        from scripts.enrich_untappd import enrich_untappd
        from scripts.enrich_breweries import enrich_breweries

        async def run_pipeline():
            print("🚀 Starting Full Enrichment Pipeline...")
            
            print("\n--- Step 1: Gemini Enrichment ---")
            await enrich_gemini(limit=args.limit, shop_filter=args.shop)
            
            print("\n--- Step 2: Untappd Enrichment ---")
            await enrich_untappd(limit=args.limit, mode='missing', shop_filter=args.shop)
            
            print("\n--- Step 3: Brewery Enrichment ---")
            # enrich_breweries does not support shop_filter, as it works on breweries found in untappd_data
            await enrich_breweries(limit=args.limit)

        asyncio.run(run_pipeline())
    elif args.command == "enrich-gemini":
        from scripts.enrich_gemini import enrich_gemini
        asyncio.run(enrich_gemini(limit=args.limit, shop_filter=args.shop))
    elif args.command == "enrich-untappd":
        from scripts.enrich_untappd import enrich_untappd
        asyncio.run(enrich_untappd(limit=args.limit, mode=args.mode, shop_filter=args.shop))
    elif args.command == "sync":
        from scripts.sync_local import sync_from_supabase
        sync_from_supabase()
    elif args.command == "clear":
        from scripts.clear_db import clear_database
        clear_database()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

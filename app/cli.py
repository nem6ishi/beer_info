import asyncio
import argparse
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))

def main():
    parser = argparse.ArgumentParser(description="Beer Info CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers and save to Supabase")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of items to scrape", default=None)

    # Enrich command (backwards compatibility - runs both Gemini + Untappd)
    enrich_parser = subparsers.add_parser("enrich", help="Run full enrichment (Gemini + Untappd) and save to Supabase")
    enrich_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    
    # Enrich Gemini only
    enrich_gemini_parser = subparsers.add_parser("enrich-gemini", help="Run Gemini enrichment only")
    enrich_gemini_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)
    
    # Enrich Untappd only
    enrich_untappd_parser = subparsers.add_parser("enrich-untappd", help="Run Untappd enrichment only")
    enrich_untappd_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)

    args = parser.parse_args()

    if args.command == "scrape":
        from scripts.scrape import scrape_to_supabase
        asyncio.run(scrape_to_supabase(limit=args.limit))
    elif args.command == "enrich":
        from scripts.enrich import enrich_supabase
        # Backwards compatibility: run old combined enrichment
        asyncio.run(enrich_supabase(limit=args.limit))
    elif args.command == "enrich-gemini":
        from scripts.enrich_gemini import enrich_gemini
        asyncio.run(enrich_gemini(limit=args.limit))
    elif args.command == "enrich-untappd":
        from scripts.enrich_untappd import enrich_untappd
        asyncio.run(enrich_untappd(limit=args.limit))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

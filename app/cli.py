import asyncio
import argparse
import sys
from app.services.scraper_service import scrape_only
from app.services.enrichment import sequential_enrichment

def main():
    parser = argparse.ArgumentParser(description="Beer Info CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scrapers only")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of items to scrape", default=None)

    # Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Run sequential enrichment")
    enrich_parser.add_argument("--limit", type=int, help="Limit number of items to enrich", default=50)

    args = parser.parse_args()

    if args.command == "scrape":
        asyncio.run(scrape_only(limit=args.limit))
    elif args.command == "enrich":
        asyncio.run(sequential_enrichment(limit=args.limit))
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

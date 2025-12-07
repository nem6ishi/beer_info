
import argparse
import asyncio
import sys
import os

# Add the project root to sys.path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.server import run_server
# Import services lazily or inside functions to avoid circular imports / early execution

def main():
    parser = argparse.ArgumentParser(description="Beer Info App CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("serve", help="Run the web server")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to run server on")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run scraper (no enrichment)")
    scrape_parser.add_argument("--limit", type=int, help="Limit number of items per scraper")

    # Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Run sequential enrichment")
    enrich_parser.add_argument("--limit", type=int, default=50, help="Number of beers to process")

    args = parser.parse_args()

    if args.command == "serve":
        run_server(port=args.port)
    elif args.command == "scrape":
        from app.services.scraper_service import scrape_only
        asyncio.run(scrape_only(limit=args.limit))
    elif args.command == "enrich":
        from app.services.enrichment import sequential_enrichment
        asyncio.run(sequential_enrichment(limit=args.limit))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

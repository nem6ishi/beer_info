# Scripts Directory

This directory contains the operational scripts for the Beer Info application.

## Active Scripts (Supabase)

These scripts interact directly with the Supabase database.

- **`scrape.py`**: Main scraper service. Scrapes beer sites and upserts data to Supabase.
- **`enrich.py`**: Legacy combined enrichment (Gemini + Untappd).
- **`enrich_gemini.py`**: Standalone Gemini enrichment.
- **`enrich_untappd.py`**: Standalone Untappd enrichment.
- **`view_data.py`**: Utility to view data from Supabase.

## Directories

- **`tests/`**: Unit tests and verification scripts.
- **`legacy/`**: Archived scripts (mostly JSON-file based workflows).

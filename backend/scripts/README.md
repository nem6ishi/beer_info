# Scripts Directory

This directory contains the operational scripts for the Beer Info application.

## Active Scripts (Supabase)

These scripts interact directly with the Supabase database.

- **`scrape.py`**: Main scraper service. Scrapes beer sites and upserts data to Supabase.
- **`view_data.py`**: Utility to view data from Supabase.
- **`enrich_gemini.py`**: Standalone Gemini enrichment.
- **`enrich_untappd.py`**: Standalone Untappd enrichment.

## Directories

- **`diagnostics/`**: Scripts for checking data integrity and various counts.
- **`maintenance/`**: Scripts for data cleaning, fixing, and one-off maintenance tasks.
- **`archive/`**: Deprecated or old scripts.
- **`tests/`**: Unit tests and verification scripts.


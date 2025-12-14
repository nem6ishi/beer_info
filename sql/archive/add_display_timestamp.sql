-- Migration: Add display_timestamp column for store display order
-- Date: 2025-12-08
-- Purpose: Maintain store display order by assigning reverse-order timestamps

-- Add display_timestamp column
ALTER TABLE beers 
ADD COLUMN IF NOT EXISTS display_timestamp TIMESTAMPTZ;

-- Create index for sorting performance
CREATE INDEX IF NOT EXISTS idx_beers_display_timestamp 
ON beers(display_timestamp DESC);

-- Backfill existing data using scrape_order
-- First scraped item (scrape_order highest) gets oldest timestamp
-- Last scraped item (scrape_order 0) gets newest timestamp
UPDATE beers 
SET display_timestamp = scrape_timestamp - (scrape_order || ' milliseconds')::INTERVAL
WHERE display_timestamp IS NULL 
  AND scrape_order IS NOT NULL 
  AND scrape_timestamp IS NOT NULL;

-- For beers without scrape_order, use scrape_timestamp as fallback
UPDATE beers 
SET display_timestamp = scrape_timestamp
WHERE display_timestamp IS NULL 
  AND scrape_timestamp IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN beers.display_timestamp IS 'Artificial timestamp for maintaining store display order. First scraped item has oldest timestamp.';

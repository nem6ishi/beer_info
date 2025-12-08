-- Migration: Remove unused and redundant columns
-- WARNING: This will permanently delete data in these columns

-- Drop redundant timestamp columns (replaced by first_seen/last_seen)
ALTER TABLE beers DROP COLUMN IF EXISTS created_at;
ALTER TABLE beers DROP COLUMN IF EXISTS updated_at;

-- Drop legacy sorting columns (replaced by display_timestamp)
ALTER TABLE beers DROP COLUMN IF EXISTS scrape_order;
ALTER TABLE beers DROP COLUMN IF EXISTS scrape_timestamp;

-- Drop redundant index
DROP INDEX IF EXISTS idx_beers_scrape_timestamp;
-- idx_beers_scrape_order might not exist but good to check, though typical DROP COLUMN handles related simple indexes? 
-- Postgres usually auto-drops indexes on dropped columns.

-- Ensure display_timestamp is properly indexed if not already
CREATE INDEX IF NOT EXISTS idx_beers_display_timestamp ON beers(display_timestamp DESC);

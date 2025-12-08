-- Remove obsolete trigger and function that reference the deleted updated_at column
DROP TRIGGER IF EXISTS update_beers_updated_at ON beers;
DROP FUNCTION IF EXISTS update_updated_at_column;

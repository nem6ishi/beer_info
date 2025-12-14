-- Remove available_since and display_timestamp columns as they are no longer needed
ALTER TABLE beers DROP COLUMN IF EXISTS available_since;
ALTER TABLE beers DROP COLUMN IF EXISTS display_timestamp;

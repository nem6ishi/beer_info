-- Remove restocked_at column as it is redundant (functionality covered by available_since)
ALTER TABLE beers DROP COLUMN IF EXISTS restocked_at;

-- Migration: Remove unique constraint from name_en in breweries table
-- This allows multiple breweries with the same name (but different URLs/countries) to coexist.

-- Step 1: Identify the constraint name (usually 'breweries_name_en_key')
-- Step 2: Drop the constraint
ALTER TABLE breweries DROP CONSTRAINT IF EXISTS breweries_name_en_key;

-- Step 3: Ensure untappd_url remains unique as the primary identifier
-- (It should already be UNIQUE based on the schema, but let's make sure)
-- ALTER TABLE breweries ADD CONSTRAINT breweries_untappd_url_key UNIQUE (untappd_url);

-- Verification: List breweries with duplicate names but different URLs
SELECT name_en, COUNT(*), array_agg(untappd_url)
FROM breweries
GROUP BY name_en
HAVING COUNT(*) > 1;

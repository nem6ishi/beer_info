-- Migration: Add numeric price column to scraped_beers
-- Run this in Supabase SQL Editor

-- 1. Add price_value column to scraped_beers
ALTER TABLE scraped_beers ADD COLUMN IF NOT EXISTS price_value NUMERIC;

-- 2. Backfill price_value from existing price string
-- Logic: Remove all non-digits, then cast to numeric.
-- Warning: This assumes 'price' contains at least some digits.
UPDATE scraped_beers
SET price_value = NULLIF(regexp_replace(price, '[^0-9]', '', 'g'), '')::numeric
WHERE price_value IS NULL;

-- 3. Update beer_info_view to use the new column
DROP VIEW IF EXISTS beer_info_view;

CREATE OR REPLACE VIEW beer_info_view AS
SELECT
  s.url,
  s.name,
  s.price,
  s.price_value, -- Use the stored numeric value
  s.image,
  s.stock_status,
  s.shop,
  s.first_seen,
  s.last_seen,
  s.untappd_url,
  
  -- Gemini Data
  g.brewery_name_en,
  g.brewery_name_jp,
  g.beer_name_en,
  g.beer_name_jp,
  
  -- Untappd Data
  u.beer_name as untappd_beer_name,
  u.brewery_name as untappd_brewery_name,
  u.style as untappd_style,
  NULLIF(regexp_replace(u.abv, '[^0-9.]', '', 'g'), '')::numeric as untappd_abv,
  NULLIF(regexp_replace(u.ibu, '[^0-9.]', '', 'g'), '')::numeric as untappd_ibu,
  NULLIF(regexp_replace(u.rating, '[^0-9.]', '', 'g'), '')::numeric as untappd_rating,
  NULLIF(regexp_replace(u.rating_count, '[^0-9.]', '', 'g'), '')::numeric as untappd_rating_count,
  u.image_url as untappd_image,
  u.fetched_at as untappd_fetched_at

FROM scraped_beers s
LEFT JOIN gemini_data g ON s.url = g.url
LEFT JOIN untappd_data u ON s.untappd_url = u.untappd_url;

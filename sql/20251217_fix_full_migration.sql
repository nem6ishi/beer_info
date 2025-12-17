-- Unified Migration: Fix Missing Columns and Update View
-- This script ensures all necessary columns exist before creating the view.

-- 1. Ensure 'breweries' table has all columns
ALTER TABLE breweries 
ADD COLUMN IF NOT EXISTS untappd_url TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS location TEXT,
ADD COLUMN IF NOT EXISTS brewery_type TEXT,
ADD COLUMN IF NOT EXISTS website TEXT,
ADD COLUMN IF NOT EXISTS stats JSONB,
ADD COLUMN IF NOT EXISTS logo_url TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 2. Ensure 'untappd_data' has the link column
ALTER TABLE untappd_data
ADD COLUMN IF NOT EXISTS untappd_brewery_url TEXT;

-- 3. Recreate the View
DROP VIEW IF EXISTS beer_info_view;

CREATE OR REPLACE VIEW beer_info_view AS
SELECT
  s.url,
  s.name,
  s.price,
  NULLIF(regexp_replace(s.price, '[^0-9]', '', 'g'), '')::numeric as price_value,
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
  u.untappd_brewery_url,
  u.fetched_at as untappd_fetched_at,

  -- Enriched Brewery Data
  b.location as brewery_location,
  b.brewery_type,
  b.logo_url as brewery_logo,
  b.id as brewery_id

FROM scraped_beers s
LEFT JOIN gemini_data g ON s.url = g.url
LEFT JOIN untappd_data u ON s.untappd_url = u.untappd_url
LEFT JOIN breweries b ON u.untappd_brewery_url = b.untappd_url;

-- Run this in Supabase SQL Editor to fix sorting for Price
-- This updates the view to cast price column from TEXT to NUMERIC (as price_value)

DROP VIEW IF EXISTS beer_info_view;

CREATE OR REPLACE VIEW beer_info_view AS
SELECT
  s.url,
  s.name,
  s.price,
  -- Extract numeric value from price string (remove non-digits except dot, handle yen sign)
  -- Assuming price format is like "¥1,000" or "1000円" or just "1000"
  -- Removing all non-numeric characters allows casting.
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
  
  -- Untappd Data (Cast to Numeric)
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

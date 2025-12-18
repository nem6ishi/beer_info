-- Fix: Change beer_info_view from SECURITY DEFINER to SECURITY INVOKER
-- This ensures RLS policies of the querying user are applied, not the view creator

-- Drop and recreate the view with security_invoker option
DROP VIEW IF EXISTS beer_info_view;

CREATE OR REPLACE VIEW beer_info_view
WITH (security_invoker = on) AS
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
  g.beer_name_en,
  g.beer_name_jp,
  g.is_set,
  
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

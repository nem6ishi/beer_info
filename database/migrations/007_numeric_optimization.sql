-- Migration 007: Numeric Optimization
-- Adds physical numeric columns to replace on-the-fly casting in views

-- 1. Update scraped_beers
ALTER TABLE scraped_beers ADD COLUMN IF NOT EXISTS price_num NUMERIC;
UPDATE scraped_beers 
SET price_num = NULLIF(regexp_replace(price, '[^0-9]', '', 'g'), '')::numeric
WHERE price_num IS NULL;

-- 2. Update untappd_data
ALTER TABLE untappd_data ADD COLUMN IF NOT EXISTS abv_num NUMERIC;
ALTER TABLE untappd_data ADD COLUMN IF NOT EXISTS ibu_num NUMERIC;
ALTER TABLE untappd_data ADD COLUMN IF NOT EXISTS rating_num NUMERIC;
ALTER TABLE untappd_data ADD COLUMN IF NOT EXISTS rating_count_num NUMERIC;

UPDATE untappd_data
SET 
  abv_num = NULLIF(regexp_replace(abv, '[^0-9.]', '', 'g'), '')::numeric,
  ibu_num = NULLIF(regexp_replace(ibu, '[^0-9.]', '', 'g'), '')::numeric,
  rating_num = NULLIF(regexp_replace(rating, '[^0-9.]', '', 'g'), '')::numeric,
  rating_count_num = NULLIF(regexp_replace(rating_count, '[^0-9.]', '', 'g'), '')::numeric
WHERE abv_num IS NULL AND rating_num IS NULL;

-- 3. Create Indices
CREATE INDEX IF NOT EXISTS idx_scraped_beers_price_num ON scraped_beers(price_num);
CREATE INDEX IF NOT EXISTS idx_untappd_data_abv_num ON untappd_data(abv_num);
CREATE INDEX IF NOT EXISTS idx_untappd_data_rating_num ON untappd_data(rating_num);

-- 4. Re-define Views
-- We use DROP ... CASCADE because CREATE OR REPLACE VIEW cannot remove or rename columns
DROP VIEW IF EXISTS beer_groups_view CASCADE;
DROP VIEW IF EXISTS beer_info_view CASCADE;

CREATE OR REPLACE VIEW beer_info_view
WITH (security_invoker = on) AS
SELECT
  s.url,
  s.name,
  s.price,
  s.price_num as price_value,
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
  g.product_type,
  g.is_set,
  
  -- Untappd Data
  u.beer_name as untappd_beer_name,
  u.brewery_name as untappd_brewery_name,
  u.style as untappd_style,
  u.abv_num as untappd_abv,
  u.ibu_num as untappd_ibu,
  u.rating_num as untappd_rating,
  u.rating_count_num as untappd_rating_count,
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

-- 5. Add beer_groups_view for optimized comparisons
CREATE OR REPLACE VIEW beer_groups_view
WITH (security_invoker = on) AS
SELECT
    untappd_url,
    MAX(untappd_beer_name) as beer_name,
    MAX(untappd_brewery_name) as brewery_name,
    MAX(untappd_style) as style,
    MAX(untappd_abv) as abv,
    MAX(untappd_ibu) as ibu,
    MAX(untappd_rating) as rating,
    MAX(untappd_rating_count) as rating_count,
    MAX(untappd_image) as beer_image,
    MAX(brewery_logo) as brewery_logo,
    MAX(brewery_location) as brewery_location,
    MAX(brewery_type) as brewery_type,
    MAX(untappd_fetched_at) as untappd_updated_at,
    bool_or(is_set) as is_set,
    MAX(product_type) as product_type,
    -- Aggregated item data
    MIN(price_value) as min_price,
    MAX(price_value) as max_price,
    MAX(first_seen) as newest_seen,
    COUNT(*) as total_items,
    json_agg(json_build_object(
        'shop', shop,
        'price', price,
        'price_value', price_value,
        'url', url,
        'stock_status', stock_status,
        'last_seen', last_seen,
        'first_seen', first_seen,
        'image', image
    )) as items
FROM beer_info_view
WHERE untappd_url IS NOT NULL 
  AND untappd_url NOT LIKE '%/search?%'
GROUP BY untappd_url;

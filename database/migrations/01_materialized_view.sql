-- 1. Drop existing views that depend on beer_info_view
DROP VIEW IF EXISTS beer_groups_view CASCADE;
DROP VIEW IF EXISTS beer_info_view CASCADE;

-- 2. Create Materialized View for beer_info_view
CREATE MATERIALIZED VIEW beer_info_view AS
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

-- 3. Add Indices to Materialized View for ultra-fast filtering
CREATE UNIQUE INDEX idx_beer_info_view_url ON beer_info_view(url);
CREATE INDEX idx_beer_info_view_first_seen ON beer_info_view(first_seen DESC);
CREATE INDEX idx_beer_info_view_price_value ON beer_info_view(price_value);
CREATE INDEX idx_beer_info_view_untappd_abv ON beer_info_view(untappd_abv);
CREATE INDEX idx_beer_info_view_untappd_ibu ON beer_info_view(untappd_ibu);
CREATE INDEX idx_beer_info_view_untappd_rating ON beer_info_view(untappd_rating DESC);
CREATE INDEX idx_beer_info_view_shop ON beer_info_view(shop);
CREATE INDEX idx_beer_info_view_untappd_style ON beer_info_view(untappd_style);
CREATE INDEX idx_beer_info_view_untappd_brewery_name ON beer_info_view(untappd_brewery_name);
CREATE INDEX idx_beer_info_view_stock_status ON beer_info_view(stock_status);
CREATE INDEX idx_beer_info_view_product_type ON beer_info_view(product_type);
CREATE INDEX idx_beer_info_view_untappd_url ON beer_info_view(untappd_url);

-- 4. Recreate beer_groups_view as a regular view based on the materialized view
CREATE VIEW beer_groups_view
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
    MIN(price_value) as min_price,
    MAX(price_value) as max_price,
    MAX(first_seen) as newest_seen,
    COUNT(*) as total_items,
    jsonb_agg(jsonb_build_object(
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

-- 5. Grant Permissions (Since it's a materialized view, we must grant explicitly)
GRANT SELECT ON beer_info_view TO anon, authenticated;
GRANT SELECT ON beer_groups_view TO anon, authenticated;

-- 6. Create RPC function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_beer_info_view()
RETURNS void AS $$
BEGIN
  -- Recompute the materialized view data
  REFRESH MATERIALIZED VIEW beer_info_view;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

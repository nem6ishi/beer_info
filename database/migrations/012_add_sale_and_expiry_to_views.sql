-- Migration: Add sale and expiry notice extraction to beer_info_view and beer_groups_view
-- Upstream references: scraped_beers(name)

DROP VIEW IF EXISTS beer_groups_view CASCADE;
DROP MATERIALIZED VIEW IF EXISTS beer_info_view CASCADE;

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
  
  -- Sale and Expiry attributes extracted from raw title
  ((s.name ~* '([0-9.]+%\s*OFF|SALE|セール|特価|割引|アウトレット|お試し|訳あり|賞味期限|在庫整理|処分|決算)') OR (s.name ~* '【[^】]*特価[^】]*】')) as is_sale,
  substring(s.name from '([0-9.]+%\s*OFF|SALE!*|セール|最終特価|特価|アウトレット|訳あり|決算セール|在庫整理|お試しセット)') as sale_tag,
  substring(s.name from '((?:賞味)?期限[^】\)]+)') as expiry_notice,
  
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
LEFT JOIN breweries b ON u.untappd_brewery_url = b.untappd_url
WHERE s.stock_status IS DISTINCT FROM 'Dead Link';

-- Add Indices to Materialized View for ultra-fast filtering
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
CREATE INDEX idx_beer_info_view_is_sale ON beer_info_view(is_sale) WHERE is_sale = TRUE;

-- Recreate beer_groups_view
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
    bool_or(is_sale) as is_sale,
    MAX(sale_tag) as sale_tag,
    MAX(expiry_notice) as expiry_notice,
    -- Aggregated item data
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
        'image', image,
        'is_sale', is_sale,
        'sale_tag', sale_tag,
        'expiry_notice', expiry_notice
    )) as items
FROM beer_info_view
WHERE untappd_url IS NOT NULL 
  AND untappd_url NOT LIKE '%/search?%'
GROUP BY untappd_url;

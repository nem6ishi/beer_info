-- Beer Information Database Schema for Supabase
-- Run this in the Supabase SQL Editor to set up the complete schema

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. scraped_beers: Raw data from scrapers
CREATE TABLE IF NOT EXISTS scraped_beers (
  url TEXT PRIMARY KEY,
  name TEXT,
  price TEXT,
  price_num NUMERIC, -- Numeric value for sorting/filtering
  image TEXT,
  stock_status TEXT,
  shop TEXT NOT NULL,
  first_seen TIMESTAMPTZ NOT NULL,
  last_seen TIMESTAMPTZ NOT NULL,
  untappd_url TEXT -- Loose link to untappd_data
);

-- 2. gemini_data: AI enriched text (linked by Product URL)
CREATE TABLE IF NOT EXISTS gemini_data (
  url TEXT PRIMARY KEY, -- References scraped_beers.url
  brewery_name_en TEXT,
  brewery_name_jp TEXT,
  beer_name_en TEXT,
  beer_name_jp TEXT,
  product_type TEXT DEFAULT 'beer',
  is_set BOOLEAN DEFAULT false,
  payload JSONB, -- Raw response for debugging
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. untappd_data: Master data for beers (ratings, stats)
CREATE TABLE IF NOT EXISTS untappd_data (
  untappd_url TEXT PRIMARY KEY,
  beer_name TEXT,
  brewery_name TEXT,
  style TEXT,
  abv TEXT,
  abv_num NUMERIC,
  ibu TEXT,
  ibu_num NUMERIC,
  rating TEXT,
  rating_num NUMERIC,
  rating_count TEXT,
  rating_count_num NUMERIC,
  image_url TEXT,
  untappd_brewery_url TEXT, -- Link to brewery page
  fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. breweries: Reference table for hints & enriched info
CREATE TABLE IF NOT EXISTS breweries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name_en TEXT,
  name_jp TEXT,
  aliases TEXT[],
  
  -- Enriched Data
  untappd_url TEXT UNIQUE,
  location TEXT,
  brewery_type TEXT,
  website TEXT,
  stats JSONB, -- {total_beers, unique_users, monthly_checkins, rating_count}
  logo_url TEXT,
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. untappd_search_failures: Track failed Untappd searches
CREATE TABLE IF NOT EXISTS untappd_search_failures (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_url TEXT NOT NULL, -- Reference to scraped_beers.url
  brewery_name TEXT,
  beer_name TEXT,
  beer_name_jp TEXT,
  failure_reason TEXT NOT NULL, -- 'missing_info', 'no_results', 'network_error', 'validation_failed'
  search_attempts INTEGER DEFAULT 1,
  last_error_message TEXT,
  first_failed_at TIMESTAMPTZ DEFAULT NOW(),
  last_failed_at TIMESTAMPTZ DEFAULT NOW(),
  resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ,
  notes TEXT
);

-- 6. Indices for Performance
CREATE INDEX IF NOT EXISTS idx_scraped_beers_shop ON scraped_beers(shop);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_last_seen ON scraped_beers(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_first_seen ON scraped_beers(first_seen DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_price_num ON scraped_beers(price_num);
-- Full-text search index (optional, but good for raw name search)
CREATE INDEX IF NOT EXISTS idx_scraped_name ON scraped_beers USING gin(to_tsvector('english', name));

-- Indices for untappd_data
CREATE INDEX IF NOT EXISTS idx_untappd_data_abv_num ON untappd_data(abv_num);
CREATE INDEX IF NOT EXISTS idx_untappd_data_rating_num ON untappd_data(rating_num);

-- Indices for untappd_search_failures
CREATE INDEX IF NOT EXISTS idx_untappd_failures_product_url ON untappd_search_failures(product_url);
CREATE INDEX IF NOT EXISTS idx_untappd_failures_resolved ON untappd_search_failures(resolved);
CREATE INDEX IF NOT EXISTS idx_untappd_failures_reason ON untappd_search_failures(failure_reason);
CREATE INDEX IF NOT EXISTS idx_untappd_failures_last_failed ON untappd_search_failures(last_failed_at DESC);


-- 7. beer_info_view: Unified view for API
-- Using physical numeric columns for speed
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
  u.untappd_brewery_url, -- Link key
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


-- 8. beer_groups_view: Unified view for grouped comparisons
-- This view aggregates items by Untappd URL for faster comparisons
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
    MAX(is_set) as is_set,
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


-- 7. Row Level Security (RLS) policies

-- Enable RLS
ALTER TABLE scraped_beers ENABLE ROW LEVEL SECURITY;
ALTER TABLE gemini_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE untappd_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE breweries ENABLE ROW LEVEL SECURITY;
ALTER TABLE untappd_search_failures ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read access (for frontend)
CREATE POLICY "Public Read Scraped" ON scraped_beers FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Gemini" ON gemini_data FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Untappd" ON untappd_data FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Breweries" ON breweries FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Failures" ON untappd_search_failures FOR SELECT TO anon USING (true);

-- Allow authenticated write access (for GitHub Actions/Scripts)
CREATE POLICY "Auth Write Scraped" ON scraped_beers FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Gemini" ON gemini_data FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Untappd" ON untappd_data FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Breweries" ON breweries FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Failures" ON untappd_search_failures FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- Function for stats (updated to work with new tables)
CREATE OR REPLACE FUNCTION get_beer_stats()
RETURNS JSON AS $$
DECLARE
  result JSON;
BEGIN
  SELECT json_build_object(
    'total_beers', COUNT(*),
    'total_shops', COUNT(DISTINCT shop),
    'beers_with_untappd', COUNT(*) FILTER (WHERE untappd_url IS NOT NULL),
    'beers_with_gemini', COUNT(*) FILTER (WHERE brewery_name_en IS NOT NULL OR brewery_name_jp IS NOT NULL),
    'last_scrape', MAX(last_seen),
    'shops', json_agg(DISTINCT shop)
  )
  INTO result
  FROM public.beer_info_view;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SET search_path = '';


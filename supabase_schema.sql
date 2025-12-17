-- Beer Information Database Schema for Supabase
-- Run this in the Supabase SQL Editor to set up the complete schema

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. scraped_beers: Raw data from scrapers
CREATE TABLE IF NOT EXISTS scraped_beers (
  url TEXT PRIMARY KEY,
  name TEXT,
  price TEXT,
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
  ibu TEXT,
  rating TEXT,
  rating_count TEXT,
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

-- 5. Indices for Performance
CREATE INDEX IF NOT EXISTS idx_scraped_beers_shop ON scraped_beers(shop);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_last_seen ON scraped_beers(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_first_seen ON scraped_beers(first_seen DESC);
-- Full-text search index (optional, but good for raw name search)
CREATE INDEX IF NOT EXISTS idx_scraped_name ON scraped_beers USING gin(to_tsvector('english', name));


-- 6. beer_info_view: Unified view for API
-- Casts prices and ratings to numeric for sorting
CREATE OR REPLACE VIEW beer_info_view AS
SELECT
  s.url,
  s.name,
  s.price,
  -- Extract numeric value from price string (remove non-digits, keep only numbers)
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
  -- Numeric casting for sorting/filtering
  NULLIF(regexp_replace(u.abv, '[^0-9.]', '', 'g'), '')::numeric as untappd_abv,
  NULLIF(regexp_replace(u.ibu, '[^0-9.]', '', 'g'), '')::numeric as untappd_ibu,
  NULLIF(regexp_replace(u.rating, '[^0-9.]', '', 'g'), '')::numeric as untappd_rating,
  NULLIF(regexp_replace(u.rating_count, '[^0-9.]', '', 'g'), '')::numeric as untappd_rating_count,
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


-- 7. Row Level Security (RLS) policies

-- Enable RLS
ALTER TABLE scraped_beers ENABLE ROW LEVEL SECURITY;
ALTER TABLE gemini_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE untappd_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE breweries ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read access (for frontend)
CREATE POLICY "Public Read Scraped" ON scraped_beers FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Gemini" ON gemini_data FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Untappd" ON untappd_data FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Breweries" ON breweries FOR SELECT TO anon USING (true);

-- Allow authenticated write access (for GitHub Actions/Scripts)
CREATE POLICY "Auth Write Scraped" ON scraped_beers FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Gemini" ON gemini_data FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Untappd" ON untappd_data FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Breweries" ON breweries FOR ALL TO authenticated USING (true) WITH CHECK (true);

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
  FROM beer_info_view;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql;


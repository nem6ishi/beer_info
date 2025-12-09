-- Migration: Normalize Database
-- Run this in the Supabase SQL Editor to restructure the database.

-- 1. Create SCRAPED_BEERS table (Stores raw shop data)
-- Note: Replaces the functionality of the old 'beers' table for raw data.
CREATE TABLE IF NOT EXISTS scraped_beers (
  url TEXT PRIMARY KEY,
  name TEXT,
  price TEXT,
  image TEXT,
  stock_status TEXT,
  shop TEXT NOT NULL,
  first_seen TIMESTAMPTZ NOT NULL,
  last_seen TIMESTAMPTZ NOT NULL,
  untappd_url TEXT -- Loose Foreign Key to untappd_data using URL
);

-- 2. Create GEMINI_DATA table (Stores AI enrichment, Linked by Product URL)
CREATE TABLE IF NOT EXISTS gemini_data (
  url TEXT PRIMARY KEY, -- References scraped_beers.url conceptually (Product URL)
  brewery_name_en TEXT,
  brewery_name_jp TEXT,
  beer_name_en TEXT,
  beer_name_jp TEXT,
  payload JSONB, -- Store raw response for debugging
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create UNTAPPD_DATA table (Stores Global Beer Master Data)
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
  fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Indices for Performance
CREATE INDEX IF NOT EXISTS idx_scraped_beers_shop ON scraped_beers(shop);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_last_seen ON scraped_beers(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_scraped_beers_first_seen ON scraped_beers(first_seen DESC);

-- 5. Row Level Security (RLS)
-- Enable RLS on all new tables
ALTER TABLE scraped_beers ENABLE ROW LEVEL SECURITY;
ALTER TABLE gemini_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE untappd_data ENABLE ROW LEVEL SECURITY;

-- Allow Anonymous Read Access (for Frontend)
CREATE POLICY "Public Read Scraped" ON scraped_beers FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Gemini" ON gemini_data FOR SELECT TO anon USING (true);
CREATE POLICY "Public Read Untappd" ON untappd_data FOR SELECT TO anon USING (true);

-- Allow Authenticated Write Access (for Scraper/Scripts)
CREATE POLICY "Auth Write Scraped" ON scraped_beers FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Gemini" ON gemini_data FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth Write Untappd" ON untappd_data FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- 6. Create View for Easy Frontend Access
-- This mimics the structure of the old 'beers' table for easier API compatibility
CREATE OR REPLACE VIEW beer_info_view AS
SELECT
  s.url,
  s.name,
  s.price,
  s.image,
  s.stock_status,
  s.shop,
  s.first_seen,
  s.last_seen,
  s.untappd_url, -- The link key
  
  -- Gemini Data
  g.brewery_name_en,
  g.brewery_name_jp,
  g.beer_name_en,
  g.beer_name_jp,
  
  -- Untappd Data
  u.beer_name as untappd_beer_name,
  u.brewery_name as untappd_brewery_name,
  u.style as untappd_style,
  u.abv as untappd_abv,
  u.ibu as untappd_ibu,
  u.rating as untappd_rating,
  u.rating_count as untappd_rating_count,
  u.image_url as untappd_image,
  u.fetched_at as untappd_fetched_at

FROM scraped_beers s
LEFT JOIN gemini_data g ON s.url = g.url
LEFT JOIN untappd_data u ON s.untappd_url = u.untappd_url;

-- Allow anonymous read on the view (requires rights on underlying tables, which we gave)
-- Note: Views don't typically have RLS themselves, they inherit.

-- 7. (Optional) Cleanup - verify data later before dropping old 'beers' table.
-- DROP TABLE IF EXISTS beers; 

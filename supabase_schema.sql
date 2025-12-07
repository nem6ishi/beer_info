-- Beer Information Database Schema for Supabase
-- Run this in the Supabase SQL Editor

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Beers table
CREATE TABLE IF NOT EXISTS beers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  url TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  price TEXT,
  image TEXT,
  stock_status TEXT,
  shop TEXT NOT NULL,
  
  -- Timestamps
  first_seen TIMESTAMPTZ NOT NULL,
  last_seen TIMESTAMPTZ NOT NULL,
  available_since TIMESTAMPTZ,
  restocked_at TIMESTAMPTZ,
  scrape_timestamp TIMESTAMPTZ,
  scrape_order INTEGER,
  
  -- Gemini extracted data
  brewery_name_jp TEXT,
  brewery_name_en TEXT,
  beer_name_jp TEXT,
  beer_name_en TEXT,
  
  -- Untappd data
  untappd_url TEXT,
  untappd_beer_name TEXT,
  untappd_brewery_name TEXT,
  untappd_style TEXT,
  untappd_abv TEXT,
  untappd_ibu TEXT,
  untappd_rating TEXT,
  untappd_rating_count TEXT,
  untappd_fetched_at TIMESTAMPTZ,
  
  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Breweries table
CREATE TABLE IF NOT EXISTS breweries (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name_en TEXT,
  name_jp TEXT,
  aliases TEXT[], -- Array of alternative names
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_beers_shop ON beers(shop);
CREATE INDEX IF NOT EXISTS idx_beers_last_seen ON beers(last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_beers_first_seen ON beers(first_seen DESC);
CREATE INDEX IF NOT EXISTS idx_beers_available_since ON beers(available_since DESC);
CREATE INDEX IF NOT EXISTS idx_beers_url ON beers(url);
CREATE INDEX IF NOT EXISTS idx_beers_name ON beers USING gin(to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_beers_brewery_name ON beers(untappd_brewery_name);

-- Full-text search index for better search performance
CREATE INDEX IF NOT EXISTS idx_beers_search ON beers USING gin(
  to_tsvector('english', 
    COALESCE(name, '') || ' ' || 
    COALESCE(beer_name_en, '') || ' ' || 
    COALESCE(beer_name_jp, '') || ' ' || 
    COALESCE(brewery_name_en, '') || ' ' || 
    COALESCE(brewery_name_jp, '') || ' ' || 
    COALESCE(untappd_brewery_name, '')
  )
);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER update_beers_updated_at
  BEFORE UPDATE ON beers
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) policies
-- Enable RLS
ALTER TABLE beers ENABLE ROW LEVEL SECURITY;
ALTER TABLE breweries ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read access (for frontend)
CREATE POLICY "Allow anonymous read access on beers"
  ON beers FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Allow anonymous read access on breweries"
  ON breweries FOR SELECT
  TO anon
  USING (true);

-- Allow authenticated write access (for GitHub Actions with service role key)
CREATE POLICY "Allow authenticated write access on beers"
  ON beers FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow authenticated write access on breweries"
  ON breweries FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Function to get beer statistics
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
    'last_scrape', MAX(scrape_timestamp),
    'shops', json_agg(DISTINCT shop)
  )
  INTO result
  FROM beers;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE beers IS 'Main table storing beer product information from Japanese craft beer shops';
COMMENT ON TABLE breweries IS 'Reference table for known breweries to improve extraction accuracy';
COMMENT ON COLUMN beers.first_seen IS 'First time this beer was discovered';
COMMENT ON COLUMN beers.last_seen IS 'Last time this beer was confirmed available';
COMMENT ON COLUMN beers.available_since IS 'When this beer became available (resets on restock)';
COMMENT ON COLUMN beers.restocked_at IS 'Last time this beer was restocked after being sold out';

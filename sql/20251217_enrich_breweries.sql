-- Migration: Enrich Breweries Table
-- Adds columns for location, type, website, stats, etc.

ALTER TABLE breweries 
ADD COLUMN IF NOT EXISTS untappd_url TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS location TEXT,
ADD COLUMN IF NOT EXISTS brewery_type TEXT,
ADD COLUMN IF NOT EXISTS website TEXT,
ADD COLUMN IF NOT EXISTS stats JSONB,
ADD COLUMN IF NOT EXISTS logo_url TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE untappd_data
ADD COLUMN IF NOT EXISTS untappd_brewery_url TEXT;

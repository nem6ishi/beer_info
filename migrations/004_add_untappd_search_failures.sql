-- Migration: Add untappd_search_failures table
-- Purpose: Track Untappd search failures for analysis and retry
-- Created: 2026-01-21

-- Create untappd_search_failures table
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

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_untappd_failures_product_url ON untappd_search_failures(product_url);
CREATE INDEX IF NOT EXISTS idx_untappd_failures_resolved ON untappd_search_failures(resolved);
CREATE INDEX IF NOT EXISTS idx_untappd_failures_reason ON untappd_search_failures(failure_reason);
CREATE INDEX IF NOT EXISTS idx_untappd_failures_last_failed ON untappd_search_failures(last_failed_at DESC);

-- Enable RLS
ALTER TABLE untappd_search_failures ENABLE ROW LEVEL SECURITY;

-- Allow anonymous read access (for potential frontend debugging UI)
CREATE POLICY "Public Read Failures" ON untappd_search_failures FOR SELECT TO anon USING (true);

-- Allow authenticated write access (for scripts)
CREATE POLICY "Auth Write Failures" ON untappd_search_failures FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- Add comment for documentation
COMMENT ON TABLE untappd_search_failures IS 'Records failed Untappd search attempts for debugging and retry';
COMMENT ON COLUMN untappd_search_failures.failure_reason IS 'Categorizes failure: missing_info, no_results, network_error, validation_failed';
COMMENT ON COLUMN untappd_search_failures.search_attempts IS 'Number of times this product has failed search';
COMMENT ON COLUMN untappd_search_failures.resolved IS 'True when successfully linked to Untappd or manually resolved';

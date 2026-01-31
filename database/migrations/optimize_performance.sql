-- Optimization Migration
-- Adds indices to improve filtering and sorting performance

-- 1. Filter Indices for Untappd Data
CREATE INDEX IF NOT EXISTS idx_untappd_style ON untappd_data(style);
CREATE INDEX IF NOT EXISTS idx_untappd_brewery ON untappd_data(brewery_name);

-- 2. Expression Indices for Numeric Sorting
-- These indices allow the DB to sort by the computed numeric value without full table scan

-- Untappd Rating (Cast to numeric)
CREATE INDEX IF NOT EXISTS idx_untappd_rating_numeric ON untappd_data ((NULLIF(regexp_replace(rating, '[^0-9.]', '', 'g'), '')::numeric));

-- Untappd ABV
CREATE INDEX IF NOT EXISTS idx_untappd_abv_numeric ON untappd_data ((NULLIF(regexp_replace(abv, '[^0-9.]', '', 'g'), '')::numeric));

-- Scraped Price
CREATE INDEX IF NOT EXISTS idx_scraped_price_numeric ON scraped_beers ((NULLIF(regexp_replace(price, '[^0-9]', '', 'g'), '')::numeric));

-- 3. Ensure First Seen index is used for default sort
-- (Already exists usually, but reinforcing)
CREATE INDEX IF NOT EXISTS idx_scraped_beers_first_seen_desc ON scraped_beers(first_seen DESC);

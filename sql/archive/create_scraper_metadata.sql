CREATE TABLE IF NOT EXISTS scraper_metadata (
    store_name TEXT PRIMARY KEY,
    last_page INTEGER,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS (Optional, but good practice)
ALTER TABLE scraper_metadata ENABLE ROW LEVEL SECURITY;

-- Allow public read/write (for now, or restricting to service role)
CREATE POLICY "Enable all access for service role" ON scraper_metadata
    USING (true)
    WITH CHECK (true);

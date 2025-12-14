-- Add untappd_url to gemini_data for better persistence
ALTER TABLE gemini_data 
ADD COLUMN IF NOT EXISTS untappd_url TEXT;

-- Add index for performance in joins
CREATE INDEX IF NOT EXISTS idx_gemini_untappd_url ON gemini_data(untappd_url);

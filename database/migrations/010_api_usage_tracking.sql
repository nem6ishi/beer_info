-- Migration 010: Create api_usage_tracking table and increment function

CREATE TABLE IF NOT EXISTS api_usage_tracking (
  service_name TEXT NOT NULL,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  request_count INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (service_name, date)
);

-- Enable RLS
ALTER TABLE api_usage_tracking ENABLE ROW LEVEL SECURITY;

-- Allow authenticated write access (for GitHub Actions/Scripts)
CREATE POLICY "Auth Write API Usage" ON api_usage_tracking FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Public Read API Usage" ON api_usage_tracking FOR SELECT TO anon USING (true);

-- Create a function to atomically increment the usage counter
CREATE OR REPLACE FUNCTION increment_api_usage(p_service_name TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_new_count INTEGER;
  v_today DATE := CURRENT_DATE;
BEGIN
  INSERT INTO api_usage_tracking (service_name, date, request_count, updated_at)
  VALUES (p_service_name, v_today, 1, NOW())
  ON CONFLICT (service_name, date)
  DO UPDATE SET 
    request_count = api_usage_tracking.request_count + 1,
    updated_at = NOW()
  RETURNING request_count INTO v_new_count;
  
  RETURN v_new_count;
END;
$$;

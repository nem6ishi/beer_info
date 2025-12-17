-- Add is_set column to gemini_data table

DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'gemini_data' AND column_name = 'is_set') THEN 
        ALTER TABLE gemini_data ADD COLUMN is_set BOOLEAN DEFAULT FALSE; 
    END IF; 
END $$;

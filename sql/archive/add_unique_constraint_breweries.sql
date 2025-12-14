-- Add unique constraint to name_en to allow upsert
ALTER TABLE breweries ADD CONSTRAINT breweries_name_en_key UNIQUE (name_en);

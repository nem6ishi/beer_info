-- Migration: Add product_type field to gemini_data
-- Replaces is_set boolean with product_type text (beer/set/glass/other)

-- Step 1: Add product_type column
ALTER TABLE gemini_data 
ADD COLUMN IF NOT EXISTS product_type TEXT 
CHECK (product_type IN ('beer', 'set', 'glass', 'other'));

-- Step 2: Migrate existing data
UPDATE gemini_data 
SET product_type = CASE 
    -- Glass products (グラス、専用グラス)
    WHEN beer_name_en ILIKE '%glass%' 
      OR beer_name_jp LIKE '%グラス%' 
      OR beer_name_en ILIKE '%glassware%' 
    THEN 'glass'
    
    -- Set products (セット商品)
    WHEN is_set = true THEN 'set'
    
    -- Default to beer for individual beers
    WHEN is_set = false OR is_set IS NULL THEN 'beer'
    
    ELSE 'beer'
END
WHERE product_type IS NULL;

-- Step 3: Create index for filtering
CREATE INDEX IF NOT EXISTS idx_gemini_product_type ON gemini_data(product_type);

-- Step 4: Drop and Recreate beer_info_view (to avoid column ordering errors)
DROP VIEW IF EXISTS beer_info_view CASCADE;

CREATE VIEW beer_info_view 
AS
SELECT
  s.url,
  s.name,
  s.price,
  NULLIF(regexp_replace(s.price, '[^0-9]', '', 'g'), '')::numeric as price_value,
  s.image,
  s.stock_status,
  s.shop,
  s.first_seen,
  s.last_seen,
  s.untappd_url,
  
  -- Gemini Data
  g.brewery_name_en,
  g.brewery_name_jp,
  g.beer_name_en,
  g.beer_name_jp,
  g.is_set,
  g.product_type,
  
  -- Untappd Data
  u.beer_name as untappd_beer_name,
  u.brewery_name as untappd_brewery_name,
  u.style as untappd_style,
  NULLIF(regexp_replace(u.abv, '[^0-9.]', '', 'g'), '')::numeric as untappd_abv,
  NULLIF(regexp_replace(u.ibu, '[^0-9.]', '', 'g'), '')::numeric as untappd_ibu,
  NULLIF(regexp_replace(u.rating, '[^0-9.]', '', 'g'), '')::numeric as untappd_rating,
  NULLIF(regexp_replace(u.rating_count, '[^0-9.]', '', 'g'), '')::numeric as untappd_rating_count,
  u.image_url as untappd_image,
  u.untappd_brewery_url,
  u.fetched_at as untappd_fetched_at,
  
  -- Enriched Brewery Data
  b.location as brewery_location,
  b.brewery_type,
  b.logo_url as brewery_logo,
  b.id as brewery_id

FROM scraped_beers s
LEFT JOIN gemini_data g ON s.url = g.url
LEFT JOIN untappd_data u ON s.untappd_url = u.untappd_url
LEFT JOIN breweries b ON u.untappd_brewery_url = b.untappd_url;

-- Step 5: Recreate dependent functions (since CASCADE might have dropped them)
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
    'last_scrape', MAX(last_seen),
    'shops', json_agg(DISTINCT shop)
  )
  INTO result
  FROM public.beer_info_view;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- Verification queries
SELECT 'Migration complete. Product type distribution:' as status;

SELECT 
  product_type, 
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM gemini_data 
WHERE product_type IS NOT NULL
GROUP BY product_type
ORDER BY count DESC;

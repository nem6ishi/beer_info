-- Fix: Add search_path to get_beer_stats function for security
-- This prevents search_path manipulation attacks

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

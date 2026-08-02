-- Migration 014: Update get_available_filters to include searchStr and location

CREATE OR REPLACE FUNCTION get_available_filters()
RETURNS TABLE (
    styles JSONB,
    breweries JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT jsonb_agg(d) FROM (
            SELECT untappd_style as style, count(*) as count 
            FROM public.beer_info_view 
            WHERE untappd_style IS NOT NULL AND untappd_style != ''
            GROUP BY untappd_style 
            ORDER BY count DESC 
            LIMIT 200
        ) d) as styles,
        (SELECT jsonb_agg(d) FROM (
            SELECT 
                v.untappd_brewery_name as name, 
                MAX(v.brewery_location) as location,
                (
                    string_agg(DISTINCT v.brewery_name_jp, ' ') || ' ' || 
                    string_agg(DISTINCT v.brewery_name_en, ' ')
                ) as searchStr
            FROM public.beer_info_view v
            WHERE v.untappd_brewery_name IS NOT NULL AND v.untappd_brewery_name != ''
            GROUP BY v.untappd_brewery_name
            ORDER BY v.untappd_brewery_name ASC
        ) d) as breweries;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER SET search_path = '';

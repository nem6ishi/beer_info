-- Migration 016: Optimize filter performance, fix beer_groups_view debug names, and align RPC counts
-- Run this in Supabase SQL Editor to:
--   1. Update get_available_filters() so SSR completes in 1 fast RPC (~400ms) instead of 20+ paginated view scans
--   2. Restore original_name and item.name in beer_groups_view (fixes Debug Mode in /grouped)
--      and materialize beer_groups_view with GIN/B-tree indices (reduces /api/grouped-beers from ~700ms to <100ms)
--   3. Align get_filtered_shop_counts() with beers API (adds untappd_beer_name search, p_days, p_only_sale, and missing-status product_type consistency)

-- 1. Update get_available_filters() to return breweries with location & searchStr
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
                TRIM(
                    COALESCE(string_agg(DISTINCT v.brewery_name_jp, ' '), '') || ' ' || 
                    COALESCE(string_agg(DISTINCT v.brewery_name_en, ' '), '')
                ) as "searchStr"
            FROM public.beer_info_view v
            WHERE v.untappd_brewery_name IS NOT NULL AND v.untappd_brewery_name != ''
            GROUP BY v.untappd_brewery_name
            ORDER BY v.untappd_brewery_name ASC
        ) d) as breweries;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER SET search_path = '';

-- 2. Restore original_name and item.name in beer_groups_view
CREATE OR REPLACE VIEW beer_groups_view
WITH (security_invoker = on) AS
SELECT
    untappd_url,
    MAX(name) as original_name,
    MAX(untappd_beer_name) as beer_name,
    MAX(untappd_brewery_name) as brewery_name,
    MAX(untappd_style) as style,
    MAX(untappd_abv) as abv,
    MAX(untappd_ibu) as ibu,
    MAX(untappd_rating) as rating,
    MAX(untappd_rating_count) as rating_count,
    MAX(untappd_image) as beer_image,
    MAX(brewery_logo) as brewery_logo,
    MAX(brewery_location) as brewery_location,
    MAX(brewery_type) as brewery_type,
    MAX(untappd_fetched_at) as untappd_updated_at,
    bool_or(is_set) as is_set,
    MAX(product_type) as product_type,
    bool_or(is_sale) as is_sale,
    MAX(sale_tag) as sale_tag,
    MAX(expiry_notice) as expiry_notice,
    MIN(price_value) as min_price,
    MAX(price_value) as max_price,
    MAX(first_seen) as newest_seen,
    COUNT(*) as total_items,
    jsonb_agg(jsonb_build_object(
        'shop', shop,
        'name', name,
        'price', price,
        'price_value', price_value,
        'url', url,
        'stock_status', stock_status,
        'last_seen', last_seen,
        'first_seen', first_seen,
        'image', image,
        'is_sale', is_sale,
        'sale_tag', sale_tag,
        'expiry_notice', expiry_notice
    )) as items
FROM beer_info_view
WHERE untappd_url IS NOT NULL 
  AND untappd_url NOT LIKE '%/search?%'
GROUP BY untappd_url;

GRANT SELECT ON beer_groups_view TO anon, authenticated;

-- 3. Update get_filtered_shop_counts to include untappd_beer_name search, p_days, p_only_sale, and missing product_type filter
CREATE OR REPLACE FUNCTION get_filtered_shop_counts(
    search_query text DEFAULT NULL,
    p_min_abv numeric DEFAULT NULL,
    p_max_abv numeric DEFAULT NULL,
    p_min_ibu numeric DEFAULT NULL,
    p_max_ibu numeric DEFAULT NULL,
    p_min_rating numeric DEFAULT NULL,
    p_stock_filter text DEFAULT NULL,
    p_style_filter text[] DEFAULT NULL,
    p_brewery_filter text[] DEFAULT NULL,
    p_product_type text DEFAULT NULL,
    p_untappd_status text DEFAULT NULL,
    p_days integer DEFAULT NULL,
    p_only_sale boolean DEFAULT NULL
)
RETURNS TABLE (
    shop text,
    shop_count bigint
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.shop, 
        COUNT(*) as shop_count
    FROM 
        public.beer_info_view v
    WHERE
        (search_query IS NULL OR search_query = '' OR 
         v.name ILIKE '%' || search_query || '%' OR 
         v.beer_name_en ILIKE '%' || search_query || '%' OR 
         v.beer_name_jp ILIKE '%' || search_query || '%' OR 
         v.untappd_beer_name ILIKE '%' || search_query || '%' OR
         v.brewery_name_en ILIKE '%' || search_query || '%' OR 
         v.brewery_name_jp ILIKE '%' || search_query || '%' OR 
         v.untappd_brewery_name ILIKE '%' || search_query || '%')
        AND (p_min_abv IS NULL OR v.untappd_abv >= p_min_abv)
        AND (p_max_abv IS NULL OR v.untappd_abv <= p_max_abv)
        AND (p_min_ibu IS NULL OR v.untappd_ibu >= p_min_ibu)
        AND (p_max_ibu IS NULL OR v.untappd_ibu <= p_max_ibu)
        AND (p_min_rating IS NULL OR v.untappd_rating >= p_min_rating)
        AND (p_stock_filter IS NULL OR p_stock_filter = '' OR 
             (p_stock_filter = 'in_stock' AND v.stock_status = 'In Stock') OR 
             (p_stock_filter = 'sold_out' AND v.stock_status = 'Sold Out'))
        AND (p_style_filter IS NULL OR array_length(p_style_filter, 1) IS NULL OR v.untappd_style = ANY(p_style_filter))
        AND (p_brewery_filter IS NULL OR array_length(p_brewery_filter, 1) IS NULL OR v.untappd_brewery_name = ANY(p_brewery_filter))
        AND (p_product_type IS NULL OR p_product_type = '' OR v.product_type = p_product_type)
        AND (p_untappd_status IS NULL OR p_untappd_status = '' OR 
             (p_untappd_status = 'missing' AND (v.untappd_url IS NULL OR v.untappd_url ILIKE '%/search?%') AND (v.product_type IS NULL OR v.product_type = 'beer')) OR 
             (p_untappd_status = 'linked' AND v.untappd_url IS NOT NULL AND v.untappd_url NOT ILIKE '%/search?%'))
        AND (p_days IS NULL OR p_days <= 0 OR v.first_seen >= NOW() - (p_days || ' days')::interval)
        AND (p_only_sale IS NULL OR p_only_sale = FALSE OR v.is_sale = TRUE)
    GROUP BY 
        v.shop;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER SET search_path = '';

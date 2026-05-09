-- Migration to add get_filtered_shop_counts RPC

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
    p_untappd_status text DEFAULT NULL
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
        beer_info_view v
    WHERE
        (search_query IS NULL OR search_query = '' OR 
         v.name ILIKE '%' || search_query || '%' OR 
         v.beer_name_en ILIKE '%' || search_query || '%' OR 
         v.beer_name_jp ILIKE '%' || search_query || '%' OR 
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
             (p_untappd_status = 'missing' AND (v.untappd_url IS NULL OR v.untappd_url ILIKE '%/search?%')) OR 
             (p_untappd_status = 'linked' AND v.untappd_url IS NOT NULL AND v.untappd_url NOT ILIKE '%/search?%'))
    GROUP BY 
        v.shop;
END;
$$ LANGUAGE plpgsql SECURITY INVOKER;

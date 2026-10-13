import { supabase } from '../lib/supabase'
import HomeClient from '../components/HomeClient'
import { Suspense } from 'react'
import { fetchAvailableFilters } from '../lib/breweries'
import type { Beer } from '../types/beer'

const BEER_INFO_VIEW_SELECT = 'url, name, price, price_value, image, stock_status, shop, first_seen, last_seen, untappd_url, untappd_enriched_at, product_type, is_set, untappd_beer_name, untappd_brewery_name, untappd_style, untappd_abv, untappd_ibu, untappd_rating, untappd_rating_count, untappd_image, brewery_location, brewery_type, brewery_logo, is_sale, sale_tag, expiry_notice, beer_name_en, beer_name_jp, brewery_name_en, brewery_name_jp';

export const revalidate = 60

export default async function Page() {
    const pageNum = 1
    const limitNum = 20
    const offset = 0

    let q = supabase.from('beer_info_view').select(BEER_INFO_VIEW_SELECT, { count: 'exact' });
    q = q.eq('stock_status', 'In Stock').order('first_seen', { ascending: false });

    // Fetch beers, shop counts, and available filters in parallel
    const [ { data: beers, count, error: dataError }, countRes, filters ] = await Promise.all([
        q.range(offset, offset + limitNum - 1),
        supabase.rpc('get_filtered_shop_counts', {
            search_query: null,
            p_min_abv: null,
            p_max_abv: null,
            p_min_ibu: null,
            p_max_ibu: null,
            p_min_rating: null,
            p_stock_filter: 'in_stock',
            p_style_filter: null,
            p_brewery_filter: null,
            p_product_type: null,
            p_untappd_status: null
        }),
        fetchAvailableFilters()
    ]);

    if (dataError) console.error('Data error:', dataError);

    if (countRes.error) console.error('Count RPC Error:', countRes.error);

    const shopCounts: Record<string, number> = {};
    if (countRes.data) {
        countRes.data.forEach((item: { shop: string; shop_count: string | number }) => {
            shopCounts[item.shop] = Number(item.shop_count);
        });
    }

    const { styles, breweries } = filters;

    const initialData = {
        beers: (beers as unknown as Beer[]) || [],
        shopCounts: shopCounts,
        pagination: {
            page: pageNum,
            limit: limitNum,
            total: count || 0,
            totalPages: Math.ceil((count || 0) / limitNum)
        }
    };

    return (
        <Suspense fallback={<div>Loading...</div>}>
            <HomeClient 
                initialData={initialData} 
                availableStyles={styles} 
                availableBreweries={breweries} 
            />
        </Suspense>
    )
}

import { supabase } from '../lib/supabase'
import HomeClient from '../components/HomeClient'
import { Suspense } from 'react'
import { fetchAvailableBreweries } from '../lib/breweries'

export const revalidate = 60

export default async function Page() {
    const pageNum = 1
    const limitNum = 20
    const offset = 0

    let q = supabase.from('beer_info_view').select('*', { count: 'exact' });
    q = q.eq('stock_status', 'In Stock').order('first_seen', { ascending: false });

    // Fetch beers, shop counts, available filters, and available breweries in parallel
    const [ { data: beers, count, error: dataError }, countRes, filterRes, breweries ] = await Promise.all([
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
        supabase.rpc('get_available_filters').single(),
        fetchAvailableBreweries()
    ]);

    if (dataError) console.error('Data error:', dataError);

    if (countRes.error) console.error('Count RPC Error:', countRes.error);
    if (filterRes.error) console.error('Filters RPC Error:', filterRes.error);

    const shopCounts: Record<string, number> = {};
    if (countRes.data) {
        countRes.data.forEach((item: { shop: string; shop_count: string | number }) => {
            shopCounts[item.shop] = Number(item.shop_count);
        });
    }

    const typedFilterData = filterRes.data as { styles?: string[] } | null;
    const styles = typedFilterData?.styles || [];

    const initialData = {
        beers: beers || [],
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

import { supabase } from '../../lib/supabase'
import GroupedClient from '../../components/GroupedClient'
import { Suspense } from 'react'

export const revalidate = 60

export default async function GroupedPage({
  searchParams,
}: {
  searchParams: { [key: string]: string | string[] | undefined }
}) {
    const page = (searchParams.page as string) || '1'
    const limit = (searchParams.limit as string) || '20'
    const search = (searchParams.search as string) || ''
    const sort = (searchParams.sort as string) || 'newest'
    
    const pageNum = parseInt(page, 10)
    const limitNum = parseInt(limit, 10)
    const offset = (pageNum - 1) * limitNum

    let q = supabase.from('beer_groups_view').select('*', { count: 'exact' });

    if (search) q = q.or(`beer_name.ilike.%${search}%,brewery_name.ilike.%${search}%`);
    if (searchParams.min_abv) q = q.gte('abv', searchParams.min_abv as string);
    if (searchParams.max_abv) q = q.lte('abv', searchParams.max_abv as string);
    if (searchParams.min_ibu) q = q.gte('ibu', searchParams.min_ibu as string);
    if (searchParams.max_ibu) q = q.lte('ibu', searchParams.max_ibu as string);
    if (searchParams.min_rating) q = q.gte('rating', searchParams.min_rating as string);
    if (searchParams.style_filter) {
        const styles = (searchParams.style_filter as string).split(',').filter(Boolean);
        if (styles.length > 0) q = q.in('style', styles);
    }
    if (searchParams.brewery_filter) {
        const breweries = (searchParams.brewery_filter as string).split(',').filter(Boolean);
        if (breweries.length > 0) q = q.in('brewery_name', breweries);
    }
    if (searchParams.product_type) q = q.eq('product_type', searchParams.product_type as string);

    switch (sort) {
        case 'newest': q = q.order('newest_seen', { ascending: false }); break;
        case 'price_asc': q = q.order('min_price', { ascending: true }); break;
        case 'price_desc': q = q.order('max_price', { ascending: false }); break;
        case 'rating_desc': q = q.order('rating', { ascending: false }); break;
        default: q = q.order('newest_seen', { ascending: false });
    }

    const { data: groups, count, error: dataError } = await q.range(offset, offset + limitNum - 1);
    if (dataError) console.error('Data error:', dataError);

    // Fetch shop counts and available filters via RPC
    const [countRes, filterRes] = await Promise.all([
        supabase.rpc('get_filtered_shop_counts', {
            search_query: search || null,
            p_min_abv: searchParams.min_abv ? parseFloat(searchParams.min_abv as string) : null,
            p_max_abv: searchParams.max_abv ? parseFloat(searchParams.max_abv as string) : null,
            p_min_ibu: searchParams.min_ibu ? parseFloat(searchParams.min_ibu as string) : null,
            p_max_ibu: searchParams.max_ibu ? parseFloat(searchParams.max_ibu as string) : null,
            p_min_rating: searchParams.min_rating ? parseFloat(searchParams.min_rating as string) : null,
            p_stock_filter: (searchParams.stock_filter as string) || null,
            p_style_filter: searchParams.style_filter ? (searchParams.style_filter as string).split(',').filter(Boolean) : null,
            p_brewery_filter: searchParams.brewery_filter ? (searchParams.brewery_filter as string).split(',').filter(Boolean) : null,
            p_product_type: (searchParams.product_type as string) || null
        }),
        supabase.rpc('get_available_filters').single()
    ]);

    if (countRes.error) console.error('Count RPC Error:', countRes.error);
    if (filterRes.error) console.error('Filters RPC Error:', filterRes.error);

    const shopCounts: Record<string, number> = {};
    if (countRes.data) {
        countRes.data.forEach((item: any) => {
            shopCounts[item.shop] = Number(item.shop_count);
        });
    }

    const typedFilterData = filterRes.data as any;
    const styles = typedFilterData?.styles || [];
    const breweries = typedFilterData?.breweries?.map((b: any) => ({
        name: b.name_en || b.name_jp || 'Unknown',
        flag: ''
    })) || [];

    const initialData = {
        groups: groups || [],
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
            <GroupedClient 
                initialData={initialData} 
                availableStyles={styles} 
                availableBreweries={breweries} 
            />
        </Suspense>
    )
}

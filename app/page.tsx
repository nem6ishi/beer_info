import { supabase } from '../lib/supabase'
import HomeClient from '../components/HomeClient'
import { Suspense } from 'react'

export const revalidate = 60

export default async function Page({
  searchParams,
}: {
  searchParams: { [key: string]: string | string[] | undefined }
}) {
    const page = (searchParams.page as string) || '1'
    const limit = (searchParams.limit as string) || '20'
    const search = (searchParams.search as string) || ''
    const sort = (searchParams.sort as string) || 'newest'
    const shop = (searchParams.shop as string) || ''
    
    const pageNum = parseInt(page, 10)
    const limitNum = parseInt(limit, 10)
    const offset = (pageNum - 1) * limitNum

    let q = supabase.from('beer_info_view').select('*', { count: 'estimated' });

    if (search) q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,brewery_name_en.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`);
    if (searchParams.min_abv) q = q.gte('untappd_abv', searchParams.min_abv as string);
    if (searchParams.max_abv) q = q.lte('untappd_abv', searchParams.max_abv as string);
    if (searchParams.min_ibu) q = q.gte('untappd_ibu', searchParams.min_ibu as string);
    if (searchParams.max_ibu) q = q.lte('untappd_ibu', searchParams.max_ibu as string);
    if (searchParams.min_rating) q = q.gte('untappd_rating', searchParams.min_rating as string);
    
    if (shop) {
        const shopList = shop.split(',').filter(Boolean);
        if (shopList.length > 0) q = q.in('shop', shopList);
    }
    if (searchParams.style_filter) {
        const styles = (searchParams.style_filter as string).split(',').filter(Boolean);
        if (styles.length > 0) q = q.in('untappd_style', styles);
    }
    if (searchParams.brewery_filter) {
        const breweries = (searchParams.brewery_filter as string).split(',').filter(Boolean);
        if (breweries.length > 0) q = q.in('untappd_brewery_name', breweries);
    }
    
    if (searchParams.stock_filter === 'in_stock') q = q.eq('stock_status', 'In Stock');
    else if (searchParams.stock_filter === 'sold_out') q = q.eq('stock_status', 'Sold Out');

    if (searchParams.untappd_status === 'missing') {
        q = q.or('untappd_url.is.null,untappd_url.ilike.%/search?%');
        q = q.or('product_type.is.null,product_type.eq.beer');
    } else if (searchParams.untappd_status === 'linked') {
        q = q.not('untappd_url', 'is', null).not('untappd_url', 'ilike', '%/search?%');
    }

    if (searchParams.product_type) q = q.eq('product_type', searchParams.product_type as string);

    switch (sort) {
        case 'newest': q = q.order('first_seen', { ascending: false }); break;
        case 'price_asc': q = q.order('price_value', { ascending: true }); break;
        case 'price_desc': q = q.order('price_value', { ascending: false }); break;
        case 'rating_desc': q = q.order('untappd_rating', { ascending: false }); break;
        default: q = q.order('first_seen', { ascending: false });
    }

    // Fetch beers, shop counts, and available filters in parallel
    const [ { data: beers, count, error: dataError }, countRes, filterRes ] = await Promise.all([
        q.range(offset, offset + limitNum - 1),
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
            p_product_type: (searchParams.product_type as string) || null,
            p_untappd_status: (searchParams.untappd_status as string) || null
        }),
        supabase.rpc('get_available_filters').single()
    ]);

    if (dataError) console.error('Data error:', dataError);

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

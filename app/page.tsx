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

    let q = supabase.from('beer_info_view').select('*', { count: 'exact' });

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

    const { data: beers, count, error: dataError } = await q.range(offset, offset + limitNum - 1);
    if (dataError) console.error('Data error:', dataError);

    // Optimized aggregation via RPC
    const { data: filterData, error: rpcError } = await supabase.rpc('get_available_filters').single();
    if (rpcError) console.error('RPC Error:', rpcError);
    
    const typedFilterData = filterData as any;
    const styles = typedFilterData?.styles || [];
    const breweries = typedFilterData?.breweries?.map((b: any) => ({
        name: b.name_en || b.name_jp || 'Unknown',
        flag: ''
    })) || [];

    const initialData = {
        beers: beers || [],
        shopCounts: {},
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

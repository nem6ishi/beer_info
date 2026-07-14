import { supabase } from '../../lib/supabase'
import { getGroupedBeers } from '../../lib/groupedBeers'
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

    const [groupedRes, filterRes] = await Promise.all([
        getGroupedBeers({
            search,
            sort,
            page: pageNum,
            limit: limitNum,
            shop: (searchParams.shop as string) || '',
            min_abv: (searchParams.min_abv as string) || null,
            max_abv: (searchParams.max_abv as string) || null,
            min_ibu: (searchParams.min_ibu as string) || null,
            max_ibu: (searchParams.max_ibu as string) || null,
            min_rating: (searchParams.min_rating as string) || null,
            style_filter: (searchParams.style_filter as string) || null,
            stock_filter: (searchParams.stock_filter as string) || null,
            product_type: (searchParams.product_type as string) || null,
            brewery_filter: (searchParams.brewery_filter as string) || null,
            days: (searchParams.days as string) || null,
            only_sale: (searchParams.only_sale as string) || null
        }),
        supabase.rpc('get_available_filters').single()
    ]);

    if (filterRes.error) console.error('Filters RPC Error:', filterRes.error);

    const { groupsData: groups, shopCounts, totalCount: count } = groupedRes;

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

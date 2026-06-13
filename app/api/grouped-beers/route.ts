import { NextResponse } from 'next/server'
import { getGroupedBeers } from '../../../lib/groupedBeers'

export async function GET(request: Request) {
    try {
        const { searchParams } = new URL(request.url)
        
        const search = searchParams.get('search') || ''
        const sort = searchParams.get('sort') || 'newest'
        const page = searchParams.get('page') || '1'
        const limit = searchParams.get('limit') || '20'
        const shop = searchParams.get('shop') || ''
        
        const min_abv = searchParams.get('min_abv')
        const max_abv = searchParams.get('max_abv')
        const min_ibu = searchParams.get('min_ibu')
        const max_ibu = searchParams.get('max_ibu')
        const min_rating = searchParams.get('min_rating')
        const style_filter = searchParams.get('style_filter')
        const stock_filter = searchParams.get('stock_filter')
        const product_type = searchParams.get('product_type')
        const brewery_filter = searchParams.get('brewery_filter')

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)

        const { groupsData, shopCounts, totalCount } = await getGroupedBeers({
            search, sort, page: pageNum, limit: limitNum, shop,
            min_abv, max_abv, min_ibu, max_ibu, min_rating,
            style_filter, stock_filter, product_type, brewery_filter
        });

        const response = NextResponse.json({
            groups: groupsData,
            shopCounts,
            pagination: {
                page: pageNum,
                limit: limitNum,
                total: totalCount,
                totalPages: Math.ceil(totalCount / limitNum)
            }
        });
        
        response.headers.set('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300');
        return response;

    } catch (error) {
        console.error('API error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

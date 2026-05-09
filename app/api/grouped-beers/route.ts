import { NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'

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
        const offset = (pageNum - 1) * limitNum

        // Build query on beer_groups_view (Pre-grouped in SQL)
        const buildQuery = () => {
            let q = supabase
                .from('beer_groups_view')
                .select('*', { count: 'exact' })

            if (search) {
                q = q.or(`beer_name.ilike.%${search}%,brewery_name.ilike.%${search}%`)
            }

            if (min_abv) q = q.gte('abv', min_abv)
            if (max_abv) q = q.lte('abv', max_abv)
            if (min_ibu) q = q.gte('ibu', min_ibu)
            if (max_ibu) q = q.lte('ibu', max_ibu)
            if (min_rating) q = q.gte('rating', min_rating)

            if (style_filter) {
                const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (styles.length > 0) q = q.in('style', styles)
            }

            if (brewery_filter) {
                const breweries = brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (breweries.length > 0) q = q.in('brewery_name', breweries)
            }

            if (product_type) {
                q = q.eq('product_type', product_type)
            }

            // Sorting
            switch (sort) {
                case 'newest':
                    q = q.order('newest_seen', { ascending: false, nullsFirst: false })
                    break
                case 'price_asc':
                    q = q.order('min_price', { ascending: true, nullsFirst: false })
                    break
                case 'price_desc':
                    q = q.order('max_price', { ascending: false, nullsFirst: false })
                    break
                case 'abv_desc':
                    q = q.order('abv', { ascending: false, nullsFirst: false })
                    break
                case 'rating_desc':
                    q = q.order('rating', { ascending: false, nullsFirst: false })
                    break
                case 'name_asc':
                    q = q.order('beer_name', { ascending: true })
                    break
                default:
                    q = q.order('newest_seen', { ascending: false, nullsFirst: false })
            }

            return q
        }

        const { data, count, error } = await buildQuery().range(offset, offset + limitNum - 1)
        if (error) throw error

        const shopCounts: Record<string, number> = {};

        const response = NextResponse.json({
            groups: data || [],
            shopCounts,
            pagination: {
                page: pageNum,
                limit: limitNum,
                total: count || 0,
                totalPages: Math.ceil((count || 0) / limitNum)
            }
        })
        
        response.headers.set('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300')
        return response

    } catch (error) {
        console.error('API error:', error)
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
    }
}

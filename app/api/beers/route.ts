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
        const untappd_status = searchParams.get('untappd_status')
        const brewery_filter = searchParams.get('brewery_filter')

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)
        const offset = (pageNum - 1) * limitNum

        // Build main query
        const buildQuery = () => {
            let q = supabase
                .from('beer_info_view')
                .select('*', { count: 'exact' })

            if (search) {
                q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
            }

            if (min_abv) q = q.gte('untappd_abv', min_abv)
            if (max_abv) q = q.lte('untappd_abv', max_abv)
            if (min_ibu) q = q.gte('untappd_ibu', min_ibu)
            if (max_ibu) q = q.lte('untappd_ibu', max_ibu)
            if (min_rating) q = q.gte('untappd_rating', min_rating)
            
            if (shop) {
                const shops = shop.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (shops.length > 0) q = q.in('shop', shops)
            }

            if (style_filter) {
                const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (styles.length > 0) q = q.in('untappd_style', styles)
            }

            if (brewery_filter) {
                const breweries = brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (breweries.length > 0) q = q.in('untappd_brewery_name', breweries)
            }

            if (stock_filter === 'in_stock') {
                q = q.eq('stock_status', 'In Stock')
            } else if (stock_filter === 'sold_out') {
                q = q.eq('stock_status', 'Sold Out')
            }

            if (untappd_status === 'missing') {
                q = q.or('untappd_url.is.null,untappd_url.ilike.%/search?%')
                q = q.or('product_type.is.null,product_type.eq.beer')
            } else if (untappd_status === 'linked') {
                q = q.not('untappd_url', 'is', null).not('untappd_url', 'ilike', '%/search?%')
            }

            if (product_type) q = q.eq('product_type', product_type)

            switch (sort) {
                case 'newest':
                    q = q.order('first_seen', { ascending: false, nullsFirst: false })
                    break
                case 'price_asc':
                    q = q.order('price_value', { ascending: true, nullsFirst: false })
                    break
                case 'price_desc':
                    q = q.order('price_value', { ascending: false, nullsFirst: false })
                    break
                case 'abv_desc':
                    q = q.order('untappd_abv', { ascending: false, nullsFirst: false })
                    break
                case 'rating_desc':
                    q = q.order('untappd_rating', { ascending: false, nullsFirst: false })
                    break
                case 'name_asc':
                    q = q.order('name', { ascending: true })
                    break
                default:
                    q = q.order('first_seen', { ascending: false, nullsFirst: false })
            }

            return q
        }

        const fetchShopCounts = async () => {
            const styles = style_filter ? style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean) : null;
            const breweries = brewery_filter ? brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean) : null;

            return supabase.rpc('get_filtered_shop_counts', {
                search_query: search || null,
                p_min_abv: min_abv ? parseFloat(min_abv) : null,
                p_max_abv: max_abv ? parseFloat(max_abv) : null,
                p_min_ibu: min_ibu ? parseFloat(min_ibu) : null,
                p_max_ibu: max_ibu ? parseFloat(max_ibu) : null,
                p_min_rating: min_rating ? parseFloat(min_rating) : null,
                p_stock_filter: stock_filter || null,
                p_style_filter: styles && styles.length > 0 ? styles : null,
                p_brewery_filter: breweries && breweries.length > 0 ? breweries : null,
                p_product_type: product_type || null,
                p_untappd_status: untappd_status || null
            });
        }

        const [dataRes, countRes] = await Promise.all([
            buildQuery().range(offset, offset + limitNum - 1),
            fetchShopCounts()
        ])

        if (dataRes.error) throw dataRes.error

        const shopCounts: Record<string, number> = {};
        if (countRes.data) {
            countRes.data.forEach((item: any) => {
                shopCounts[item.shop] = Number(item.shop_count);
            });
        }

        const response = NextResponse.json({
            beers: dataRes.data || [],
            shopCounts,
            pagination: {
                page: pageNum,
                limit: limitNum,
                total: dataRes.count || 0,
                totalPages: Math.ceil((dataRes.count || 0) / limitNum)
            }
        })
        
        response.headers.set('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=300')
        return response

    } catch (error) {
        console.error('API error:', error)
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
    }
}

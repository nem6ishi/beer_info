import type { NextApiRequest, NextApiResponse } from 'next'
import { supabase } from '../../lib/supabase'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' })
    }

    try {
        const search = (req.query.search as string) || ''
        const sort = (req.query.sort as string) || 'newest'
        const page = (req.query.page as string) || '1'
        const limit = (req.query.limit as string) || '100'
        const shop = (req.query.shop as string) || ''
        
        const {
            min_abv,
            max_abv,
            min_ibu,
            max_ibu,
            min_rating,
            style_filter,
            stock_filter,
            product_type
        } = req.query as Record<string, string | undefined>

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)
        const offset = (pageNum - 1) * limitNum

        // Build main query
        const buildQuery = () => {
            let q = supabase
                .from('beer_info_view')
                .select('*', { count: 'exact' })

            // Apply search filter if provided
            if (search) {
                q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
            }

            // Apply advanced filters using NUMERIC columns via the view (which now uses physical columns)
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

            if (req.query.brewery_filter) {
                const breweries = (req.query.brewery_filter as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (breweries.length > 0) q = q.in('untappd_brewery_name', breweries)
            }

            if (stock_filter === 'in_stock') {
                q = q.eq('stock_status', 'In Stock')
            } else if (stock_filter === 'sold_out') {
                q = q.eq('stock_status', 'Sold Out')
            }

            if (req.query.untappd_status === 'missing') {
                q = q.or('untappd_url.is.null,untappd_url.ilike.%/search?%')
                q = q.or('product_type.is.null,product_type.eq.beer')
            } else if (req.query.untappd_status === 'linked') {
                q = q.not('untappd_url', 'is', null).not('untappd_url', 'ilike', '%/search?%')
            }

            if (product_type) q = q.eq('product_type', product_type)

            // Sorting
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

        // Build count query (for shop filters)
        const buildCountQuery = () => {
            let q = supabase
                .from('beer_info_view')
                .select('shop')

            if (search) {
                q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
            }
            if (min_abv) q = q.gte('untappd_abv', min_abv)
            if (max_abv) q = q.lte('untappd_abv', max_abv)
            if (min_ibu) q = q.gte('untappd_ibu', min_ibu)
            if (max_ibu) q = q.lte('untappd_ibu', max_ibu)
            if (min_rating) q = q.gte('untappd_rating', min_rating)
            if (stock_filter === 'in_stock') q = q.eq('stock_status', 'In Stock')
            else if (stock_filter === 'sold_out') q = q.eq('stock_status', 'Sold Out')
            if (style_filter) {
                const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (styles.length > 0) q = q.in('untappd_style', styles)
            }
            if (req.query.brewery_filter) {
                const breweries = (req.query.brewery_filter as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (breweries.length > 0) q = q.in('untappd_brewery_name', breweries)
            }
            if (product_type) q = q.eq('product_type', product_type)
            if (req.query.untappd_status === 'missing') {
                q = q.or('untappd_url.is.null,untappd_url.ilike.%/search?%')
            } else if (req.query.untappd_status === 'linked') {
                q = q.not('untappd_url', 'is', null).not('untappd_url', 'ilike', '%/search?%')
            }
            return q
        }

        // Parallel execution
        const [dataRes, countRes] = await Promise.all([
            buildQuery().range(offset, offset + limitNum - 1),
            buildCountQuery().limit(1000).select('shop') // Reduce to 1000 to avoid 500 errors
        ])

        if (dataRes.error) throw dataRes.error

        const shopCounts: Record<string, number> = {};
        if (countRes.data) {
            countRes.data.forEach(item => {
                shopCounts[item.shop] = (shopCounts[item.shop] || 0) + 1;
            });
        }

        return res.status(200).json({
            beers: dataRes.data || [],
            shopCounts,
            pagination: {
                page: pageNum,
                limit: limitNum,
                total: dataRes.count || 0,
                totalPages: Math.ceil((dataRes.count || 0) / limitNum)
            }
        })
    } catch (error) {
        console.error('API error:', error)
        return res.status(500).json({ error: 'Internal server error' })
    }
}

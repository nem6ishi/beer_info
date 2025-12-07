import { supabase } from '../../lib/supabase'

export default async function handler(req, res) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' })
    }

    try {
        const {
            search = '',
            sort = 'newest',
            page = '1',
            limit = '100'
        } = req.query

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)
        const offset = (pageNum - 1) * limitNum

        // Build query
        let query = supabase
            .from('beers')
            .select('*', { count: 'exact' })

        // Apply search filter if provided
        if (search) {
            query = query.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
        }

        // Sorting
        switch (sort) {
            case 'newest':
                query = query
                    .order('scrape_timestamp', { ascending: false })
                    .order('scrape_order', { ascending: true })
                break
            case 'price_asc':
                // Note: price is stored as text, so this might need custom handling
                query = query.order('price', { ascending: true })
                break
            case 'price_desc':
                query = query.order('price', { ascending: false })
                break
            case 'abv_desc':
                query = query.order('untappd_abv', { ascending: false, nullsFirst: false })
                break
            case 'rating_desc':
                query = query.order('untappd_rating', { ascending: false, nullsFirst: false })
                break
            case 'name_asc':
                query = query.order('name', { ascending: true })
                break
            default:
                query = query
                    .order('scrape_timestamp', { ascending: false })
                    .order('scrape_order', { ascending: true })
        }

        // Pagination
        query = query.range(offset, offset + limitNum - 1)

        const { data, error, count } = await query

        if (error) {
            console.error('Supabase error:', error)
            return res.status(500).json({ error: 'Database query failed' })
        }

        return res.status(200).json({
            beers: data || [],
            pagination: {
                page: pageNum,
                limit: limitNum,
                total: count || 0,
                totalPages: Math.ceil((count || 0) / limitNum)
            }
        })
    } catch (error) {
        console.error('API error:', error)
        return res.status(500).json({ error: 'Internal server error' })
    }
}

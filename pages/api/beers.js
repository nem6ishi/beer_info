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
            limit = '100',
            shop = '',
            min_abv,
            max_abv,
            min_ibu,
            max_ibu,
            min_rating,
            style_filter,
            stock_filter,
            missing_untappd,
            set_mode
        } = req.query

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)
        const offset = (pageNum - 1) * limitNum

        // Build query
        let query = supabase
            .from('beer_info_view')
            .select('*', { count: 'exact' })

        // Apply search filter if provided
        if (search) {
            query = query.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
        }

        // Apply advanced filters
        if (min_abv) query = query.gte('untappd_abv', min_abv)
        if (max_abv) query = query.lte('untappd_abv', max_abv)
        if (min_ibu) query = query.gte('untappd_ibu', min_ibu)
        if (max_ibu) query = query.lte('untappd_ibu', max_ibu)
        if (min_rating) query = query.gte('untappd_rating', min_rating)
        // Filter by Shop (Multi-select)
        if (shop) {
            const shops = shop.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
            if (shops.length > 0) {
                query = query.in('shop', shops)
            }
        }

        // Filter by Style (Multi-select)
        if (style_filter) {
            const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
            if (styles.length > 0) {
                query = query.in('untappd_style', styles)
            }
        }

        // Filter by Brewery (Multi-select)
        if (req.query.brewery_filter) {
            const breweries = req.query.brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
            if (breweries.length > 0) {
                query = query.in('untappd_brewery_name', breweries)
            }
        } if (stock_filter === 'in_stock') {
            // Assuming stock_status contains 'In Stock' or similar
            // Using ilike to be safe, or check data. Usually it's 'In Stock' or 'Sold Out'
            // Let's assume 'In Stock' for now based on style.css (.stock-badge.in-stock)
            // But checking partial match
            query = query.ilike('stock_status', '%In Stock%')
        }

        // Filter by Untappd Status
        if (req.query.untappd_status === 'missing') {
            query = query.or('untappd_url.is.null,untappd_url.ilike.%/search?%')
            // Exclude sets from 'missing' list (they often don't have links mostly)
            query = query.or('is_set.is.null,is_set.eq.false')
        } else if (req.query.untappd_status === 'linked') {
            query = query.not('untappd_url', 'is', null).not('untappd_url', 'ilike', '%/search?%')
        }

        // Filter by Set Mode
        if (set_mode === 'individual') {
            // is_set is typically false or null
            query = query.or('is_set.is.null,is_set.eq.false')
        } else if (set_mode === 'set') {
            query = query.eq('is_set', true)
        }

        // Sorting
        switch (sort) {
            case 'newest':
                // Sort by first_seen (newest = most recently seen/added)
                query = query
                    .order('first_seen', { ascending: false, nullsLast: true })
                break
            case 'price_asc':
                // Use numeric price_value column, NULLS LAST
                query = query.order('price_value', { ascending: true, nullsFirst: false })
                break
            case 'price_desc':
                // Price High to Low, NULLS LAST (so unknowns are at bottom)
                // Trying nullsFirst: false to force different behavior if nullsLast is ignored
                query = query.order('price_value', { ascending: false, nullsFirst: false })
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
                // Default: newest first (first_seen)
                query = query
                    .order('first_seen', { ascending: false, nullsLast: true })
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

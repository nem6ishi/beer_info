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
            stock_filter
        } = req.query

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)
        const offset = (pageNum - 1) * limitNum

        // Build query
        let query = supabase
            .from('beer_info_view')
            .select('*', { count: 'exact' })

        // Apply shop filter if provided
        if (shop) {
            query = query.eq('shop', shop)
        }

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
            const shops = shop.split(',').map(s => s.trim()).filter(Boolean)
            if (shops.length > 0) {
                query = query.in('shop', shops)
            }
        }

        // Filter by Style (Multi-select)
        if (style_filter) {
            // Logic: style_filter is now a list of exact styles from the DB (e.g. "IPA", "Stout")
            // We generally use exact match if we are providing a dropdown of existing styles.
            // But previously it was partial match (ilike).
            // Since we are moving to a multi-select dropdown of *existing* styles, .in() is appropriate.
            // HOWEVER, if the user still wants to type "IPA" and find "IPA - American", that's different.
            // The requirement says "gather styles from untappd db and make checklist". 
            // So .in() on the exact style name is the correct approach for a checklist.

            const styles = style_filter.split(',').map(s => s.trim()).filter(Boolean)
            if (styles.length > 0) {
                query = query.in('untappd_style', styles)
            }
        } if (stock_filter === 'in_stock') {
            // Assuming stock_status contains 'In Stock' or similar
            // Using ilike to be safe, or check data. Usually it's 'In Stock' or 'Sold Out'
            // Let's assume 'In Stock' for now based on style.css (.stock-badge.in-stock)
            // But checking partial match
            query = query.ilike('stock_status', '%In Stock%')
        }

        // Sorting
        switch (sort) {
            case 'newest':
                // Sort by first_seen (newest = most recently seen/added)
                query = query
                    .order('first_seen', { ascending: false, nullsLast: true })
                break
            case 'price_asc':
                // Use numeric price_value column
                query = query.order('price_value', { ascending: true })
                break
            case 'price_desc':
                query = query.order('price_value', { ascending: false })
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

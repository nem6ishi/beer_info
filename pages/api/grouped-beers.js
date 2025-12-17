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
            limit = '20',
            shop = '',
            min_abv,
            max_abv,
            min_ibu,
            max_ibu,
            min_rating,
            style_filter,
            stock_filter,
            missing_untappd
        } = req.query

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)

        // Build query
        let query = supabase
            .from('beer_info_view')
            .select('*')
            // Crucial: Only fetch items with untappd_url for grouping
            .not('untappd_url', 'is', null)
            // Exclude search result pages, we want actual beer pages
            .not('untappd_url', 'ilike', '%/search?%')
            // Optimize: Order by newest first so the first item found for a group is the newest variant
            .order('first_seen', { ascending: false, nullsLast: true })

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
            const styles = style_filter.split(',').map(s => s.trim()).filter(Boolean)
            if (styles.length > 0) {
                query = query.in('untappd_style', styles)
            }
        }

        // Filter by Brewery (Multi-select)
        if (req.query.brewery_filter) {
            const breweries = req.query.brewery_filter.split(',').map(s => s.trim()).filter(Boolean)
            if (breweries.length > 0) {
                query = query.in('untappd_brewery_name', breweries)
            }
        }

        if (stock_filter === 'in_stock') {
            query = query.ilike('stock_status', '%In Stock%')
        }

        // Note: missing_untappd filter is ignored/irrelevant here as we enforce presence of untappd_url

        // Fetch ALL matching data (no pagination in DB query)
        const { data, error } = await query

        if (error) {
            console.error('Supabase error:', error)
            return res.status(500).json({ error: 'Database query failed' })
        }

        if (!data || data.length === 0) {
            return res.status(200).json({
                groups: [],
                pagination: {
                    page: pageNum,
                    limit: limitNum,
                    total: 0,
                    totalPages: 0
                }
            })
        }

        // Grouping Logic
        const groupsMap = new Map()

        data.forEach(item => {
            const key = item.untappd_url
            if (!groupsMap.has(key)) {
                groupsMap.set(key, {
                    // Representative data (use the first one encountered)
                    // Since query is ordered by first_seen DESC, this will be the NEWEST item.
                    untappd_url: key,
                    beer_name: item.untappd_beer_name || item.name, // Prefer Untappd > Raw
                    beer_image: item.untappd_image || item.image,
                    style: item.untappd_style || item.style,
                    abv: item.untappd_abv,
                    ibu: item.untappd_ibu,
                    rating: item.untappd_rating,
                    brewery: item.untappd_brewery_name,
                    brewery_logo: item.brewery_logo,
                    brewery_location: item.brewery_location,
                    brewery_type: item.brewery_type,
                    untappd_updated_at: item.untappd_fetched_at, // Add timestamp
                    rating_count: item.untappd_rating_count,
                    // Aggregate data
                    items: [],
                    // Sort key helpers
                    min_price: Infinity,
                    max_price: -Infinity,
                    newest_seen: '',
                    total_stock: 0
                })
            }

            const group = groupsMap.get(key)
            group.items.push({
                shop: item.shop,
                price: item.price,
                price_value: item.price_value,
                url: item.url,
                stock_status: item.stock_status,
                last_seen: item.last_seen,
                first_seen: item.first_seen,
                image: item.image // Add image for fallback logic
            })

            // Update stats
            if (item.price_value) {
                if (item.price_value < group.min_price) group.min_price = item.price_value
                if (item.price_value > group.max_price) group.max_price = item.price_value
            }
            if (!group.newest_seen || (item.first_seen && item.first_seen > group.newest_seen)) {
                group.newest_seen = item.first_seen
            }
        })

        // Convert Map to Array
        let groups = Array.from(groupsMap.values())

        // Post-processing: Handle Infinity min_price for items with no price
        groups.forEach(g => {
            if (g.min_price === Infinity) g.min_price = 0
            if (g.max_price === -Infinity) g.max_price = 0
        })

        // Sorting Groups
        switch (sort) {
            case 'newest':
                groups.sort((a, b) => {
                    const dateA = new Date(a.newest_seen || 0).getTime()
                    const dateB = new Date(b.newest_seen || 0).getTime()
                    return dateB - dateA
                })
                break
            case 'price_asc':
                // Sort by min_price
                groups.sort((a, b) => {
                    if (a.min_price === 0 && b.min_price !== 0) return 1 // No price last
                    if (a.min_price !== 0 && b.min_price === 0) return -1
                    return a.min_price - b.min_price
                })
                break
            case 'price_desc':
                // Sort by max_price
                groups.sort((a, b) => b.max_price - a.max_price)
                break
            case 'abv_desc':
                groups.sort((a, b) => (b.abv || 0) - (a.abv || 0))
                break
            case 'rating_desc':
                groups.sort((a, b) => (b.rating || 0) - (a.rating || 0))
                break
            case 'name_asc':
                groups.sort((a, b) => (a.beer_name || '').localeCompare(b.beer_name || ''))
                break
            default:
                groups.sort((a, b) => {
                    const dateA = new Date(a.newest_seen || 0).getTime()
                    const dateB = new Date(b.newest_seen || 0).getTime()
                    return dateB - dateA
                })
        }

        // Pagination
        const totalGroups = groups.length
        const totalPages = Math.ceil(totalGroups / limitNum)

        // Slice
        const offset = (pageNum - 1) * limitNum
        const paginatedGroups = groups.slice(offset, offset + limitNum)

        return res.status(200).json({
            groups: paginatedGroups,
            pagination: {
                page: pageNum,
                limit: limitNum,
                total: totalGroups,
                totalPages: totalPages
            }
        })

    } catch (error) {
        console.error('API error:', error)
        return res.status(500).json({ error: 'Internal server error' })
    }
}

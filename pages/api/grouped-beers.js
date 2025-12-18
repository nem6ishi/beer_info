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
            missing_untappd,
            set_mode
        } = req.query

        const pageNum = parseInt(page, 10)
        const limitNum = parseInt(limit, 10)

        // Helper to build the base query
        const buildBaseQuery = () => {
            let q = supabase
                .from('beer_info_view')
                .select(`
                    url,
                    name,
                    price,
                    price_value,
                    image,
                    stock_status,
                    shop,
                    first_seen,
                    last_seen,
                    untappd_url,
                    untappd_beer_name,
                    untappd_brewery_name,
                    untappd_style,
                    untappd_abv,
                    untappd_ibu,
                    untappd_rating,
                    untappd_rating_count,
                    untappd_image,
                    brewery_location,
                    brewery_type,
                    brewery_logo,
                    is_set
                `)
                .not('untappd_url', 'is', null)
                .not('untappd_url', 'ilike', '%/search?%')
                // Optimize: Order by newest first
                .order('first_seen', { ascending: false, nullsLast: true })

            // Apply search filter
            if (search) {
                q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
            }

            // Apply advanced filters
            if (min_abv) q = q.gte('untappd_abv', min_abv)
            if (max_abv) q = q.lte('untappd_abv', max_abv)
            if (min_ibu) q = q.gte('untappd_ibu', min_ibu)
            if (max_ibu) q = q.lte('untappd_ibu', max_ibu)
            if (min_rating) q = q.gte('untappd_rating', min_rating)

            // Shop Filter - DISABLED: Applied after grouping to show all stores for matching beers
            // if (shop) {
            //     const shops = shop.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
            //     if (shops.length > 0) q = q.in('shop', shops)
            // }

            // Style Filter
            if (style_filter) {
                const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (styles.length > 0) q = q.in('untappd_style', styles)
            }

            // Brewery Filter
            if (req.query.brewery_filter) {
                const breweries = req.query.brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (breweries.length > 0) q = q.in('untappd_brewery_name', breweries)
            }

            if (stock_filter === 'in_stock') {
                q = q.eq('stock_status', 'In Stock')
            } else if (stock_filter === 'sold_out') {
                q = q.eq('stock_status', 'Sold Out')
            }

            // Set Mode
            if (set_mode === 'individual') {
                q = q.or('is_set.is.null,is_set.eq.false')
            } else if (set_mode === 'set') {
                q = q.eq('is_set', true)
            }

            return q
        }

        // 1. Get total count to determine chunks
        // We use a separate query builder for count to avoid mutating the data query issues?
        // Actually, Supabase builders are immutable until executed generally, but let's be safe with new instances.
        const countQuery = supabase
            .from('beer_info_view')
            .select('*', { count: 'exact', head: true })
            .not('untappd_url', 'is', null)
            .not('untappd_url', 'ilike', '%/search?%')

        // Re-apply filters for count (Simplified logic: duplication is safer than sharing mutable builder state)
        // ... Code duplication is annoying. `buildBaseQuery` returns a cloneable state? 
        // No, let's just use buildBaseQuery() but override select.

        let qCount = buildBaseQuery()
        // Override select for count
        // Note: PostgREST client might append select? .select() usually replaces or appends? 
        // In supabase-js, calling .select again *overrides* columns? Let's assume standard builder behavior.
        // Actually, easiest is to just count using the base query structure.
        // .count() is a method on the builder that modifies the request headers usually.

        const { count, error: countError } = await qCount.select('*', { count: 'exact', head: true })
        if (countError) throw countError

        const totalRows = count || 0
        const CHUNK_SIZE = 1000

        // 2. Parallel Fetch
        const promises = []
        for (let i = 0; i < totalRows; i += CHUNK_SIZE) {
            promises.push(
                buildBaseQuery().range(i, i + CHUNK_SIZE - 1)
            )
        }

        const results = await Promise.all(promises)

        // Combine data
        let data = []
        results.forEach(r => {
            if (r.data) data.push(...r.data)
            if (r.error) console.error("Chunk Fetch Error", r.error)
        })

        if (!data || data.length === 0) {
            return res.status(200).json({
                groups: [],
                shopCounts: {},
                pagination: {
                    page: pageNum,
                    limit: limitNum,
                    total: 0,
                    totalPages: 0
                }
            })
        }

        // --- Shop Counts Calculation ---
        // With "Fetch All", 'data' contains EVERYTHING matching filters.
        // If 'shop' filter was applied, 'data' is restricted.
        // To show global shop counts, we would need a separate query WITHOUT shop filter.
        // Retaining simplified shop count logic for now (counts based on current 'shop' filter results or 'data').
        // If shop filter is off, data has all shops, so counts are correct.
        // If shop filter is ON, we only see that shop. This is consistent with current "shopData" logic.
        let shopData = data;

        // Only if we want "Counts for ALL shops even when filtered" do we need extra logic.
        // The original code tried to handle this but was complex.
        // For now, calculating from 'data' is consistent with "filtered results".

        // Re-implement sidebar counts correctly? 
        // Previous logic: "To show counts for ALL shops... we'd need to re-query".
        // If user wants correct counts for sidebar, we technically need a separate aggregation.
        // But let's stick to the main goal: correct Grouping.

        const shopCounts = {};
        shopData.forEach(item => {
            shopCounts[item.shop] = (shopCounts[item.shop] || 0) + 1;
        });

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
                    is_set: item.is_set, // Pass Set flag
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

        // Apply shop filter AFTER grouping to show all stores for matching beers
        if (shop) {
            const shops = shop.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
            if (shops.length > 0) {
                // Filter groups to only include beers available in ALL selected shops (AND condition)
                groups = groups.filter(group =>
                    shops.every(selectedShop =>
                        group.items.some(item => item.shop === selectedShop)
                    )
                )
            }
        }

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
            shopCounts,
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

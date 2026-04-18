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
        const limit = (req.query.limit as string) || '20'
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

        const pageNum = parseInt(page as string, 10)
        const limitNum = parseInt(limit as string, 10)

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
                    untappd_fetched_at,
                    brewery_location,
                    brewery_type,
                    brewery_logo,
                    is_set,
                    product_type
                `)
                .not('untappd_url', 'is', null)
                .not('untappd_url', 'ilike', '%/search?%')
                .order('first_seen', { ascending: false, nullsFirst: false })

            if (search) {
                q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
            }

            if (min_abv) q = q.gte('untappd_abv', min_abv as string)
            if (max_abv) q = q.lte('untappd_abv', max_abv as string)
            if (min_ibu) q = q.gte('untappd_ibu', min_ibu as string)
            if (max_ibu) q = q.lte('untappd_ibu', max_ibu as string)
            if (min_rating) q = q.gte('untappd_rating', min_rating as string)

            if (style_filter) {
                const styles = (style_filter as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
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

            if (product_type) {
                q = q.eq('product_type', product_type as string)
            }

            return q
        }

        // 1. Get total count
        const buildCountQuery = () => {
            let q = supabase
                .from('beer_info_view')
                .select('*', { count: 'exact', head: true })
                .not('untappd_url', 'is', null)
                .not('untappd_url', 'ilike', '%/search?%')

            if (search) {
                q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,beer_name_jp.ilike.%${search}%,brewery_name_en.ilike.%${search}%,brewery_name_jp.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`)
            }

            if (min_abv) q = q.gte('untappd_abv', min_abv as string)
            if (max_abv) q = q.lte('untappd_abv', max_abv as string)
            if (min_ibu) q = q.gte('untappd_ibu', min_ibu as string)
            if (max_ibu) q = q.lte('untappd_ibu', max_ibu as string)
            if (min_rating) q = q.gte('untappd_rating', min_rating as string)

            if (style_filter) {
                const styles = (style_filter as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
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

            if (product_type) {
                q = q.eq('product_type', product_type as string)
            }

            return q
        }

        const { count, error: countError } = await buildCountQuery()
        if (countError) throw countError

        const totalRows = count || 0
        const CHUNK_SIZE = 1000

        const promises = []
        for (let i = 0; i < totalRows; i += CHUNK_SIZE) {
            promises.push(
                buildBaseQuery().range(i, i + CHUNK_SIZE - 1)
            )
        }

        const results = await Promise.all(promises)

        let data: any[] = []
        results.forEach(r => {
            if (r.data) data.push(...r.data)
        })

        if (data.length === 0) {
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

        const shopCounts: Record<string, number> = {};
        data.forEach(item => {
            shopCounts[item.shop] = (shopCounts[item.shop] || 0) + 1;
        });

        const groupsMap = new Map<string, any>()

        data.forEach(item => {
            const key = item.untappd_url
            if (!groupsMap.has(key)) {
                groupsMap.set(key, {
                    untappd_url: key,
                    beer_name: item.untappd_beer_name || item.name,
                    beer_image: item.untappd_image || item.image,
                    style: item.untappd_style || item.style,
                    abv: item.untappd_abv,
                    ibu: item.untappd_ibu,
                    rating: item.untappd_rating,
                    brewery: item.untappd_brewery_name,
                    brewery_logo: item.brewery_logo,
                    brewery_location: item.brewery_location,
                    brewery_type: item.brewery_type,
                    untappd_updated_at: item.untappd_fetched_at,
                    rating_count: item.untappd_rating_count,
                    is_set: item.is_set,
                    product_type: item.product_type,
                    items: [],
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
                image: item.image
            })

            if (item.price_value) {
                if (item.price_value < group.min_price) group.min_price = item.price_value
                if (item.price_value > group.max_price) group.max_price = item.price_value
            }
            if (!group.newest_seen || (item.first_seen && item.first_seen > group.newest_seen)) {
                group.newest_seen = item.first_seen
            }
        })

        let groups = Array.from(groupsMap.values())

        groups.forEach(g => {
            if (g.min_price === Infinity) g.min_price = 0
            if (g.max_price === -Infinity) g.max_price = 0
        })

        if (shop) {
            const shops = (shop as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
            if (shops.length > 0) {
                groups = groups.filter(group =>
                    shops.every(selectedShop =>
                        group.items.some((item: any) => item.shop === selectedShop)
                    )
                )
            }
        }

        switch (sort) {
            case 'newest':
                groups.sort((a, b) => new Date(b.newest_seen || 0).getTime() - new Date(a.newest_seen || 0).getTime())
                break
            case 'price_asc':
                groups.sort((a, b) => {
                    if (a.min_price === 0 && b.min_price !== 0) return 1
                    if (a.min_price !== 0 && b.min_price === 0) return -1
                    return a.min_price - b.min_price
                })
                break
            case 'price_desc':
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
                groups.sort((a, b) => new Date(b.newest_seen || 0).getTime() - new Date(a.newest_seen || 0).getTime())
        }

        const totalGroups = groups.length
        const totalPages = Math.ceil(totalGroups / limitNum)
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

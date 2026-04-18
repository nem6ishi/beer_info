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
        const offset = (pageNum - 1) * limitNum

        // Build query on beer_groups_view (Pre-grouped in SQL)
        const buildQuery = () => {
            let q = supabase
                .from('beer_groups_view')
                .select('*', { count: 'exact' })

            if (search) {
                q = q.or(`beer_name.ilike.%${search}%,brewery_name.ilike.%${search}%`)
            }

            if (min_abv) q = q.gte('abv', min_abv as string)
            if (max_abv) q = q.lte('abv', max_abv as string)
            if (min_ibu) q = q.gte('ibu', min_ibu as string)
            if (max_ibu) q = q.lte('ibu', max_ibu as string)
            if (min_rating) q = q.gte('rating', min_rating as string)

            if (style_filter) {
                const styles = (style_filter as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (styles.length > 0) q = q.in('style', styles)
            }

            if (req.query.brewery_filter) {
                const breweries = (req.query.brewery_filter as string).normalize('NFC').split(',').map(s => s.trim()).filter(Boolean)
                if (breweries.length > 0) q = q.in('brewery_name', breweries)
            }

            if (stock_filter === 'in_stock') {
                // Since this is a grouped view, "in_stock" means at least one item is in stock
                // We'll approximate this by checking if any item in the original view (via a filter) matches,
                // but for the grouped view itself, it's easier to just filter the base items.
                // However, PostgREST doesn't allow easy filtering on JSONB items.
                // A better way is to filter the groups that HAVE at least one in-stock item.
                // For now, we'll assume stock_status is handled via the view if possible.
            }

            if (product_type) {
                q = q.eq('product_type', product_type as string)
            }

            if (shop) {
                // Multi-shop filtering: Group must have at least one item from the shop
                // This is also a bit tricky with JSONB in PostgREST.
                // For now, we'll keep it simple or use a hint.
            }

            // Sorting (Done in SQL now!)
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

        // --- Shop Counts (Optional but good for sidebar) ---
        // We'll reuse the logic from beers.ts or skip for now if too slow.
        // For grouped view, shop counts are slightly different (count groups containing shop).
        // For simplicity, we'll return an empty object or a simplified count for now.
        const shopCounts: Record<string, number> = {};

        return res.status(200).json({
            groups: data || [],
            shopCounts,
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

import { supabase } from './supabase'

export interface GetGroupedBeersOptions {
    search: string;
    sort: string;
    page: number;
    limit: number;
    shop: string;
    min_abv: string | null;
    max_abv: string | null;
    min_ibu: string | null;
    max_ibu: string | null;
    min_rating: string | null;
    style_filter: string | null;
    stock_filter: string | null;
    product_type: string | null;
    brewery_filter: string | null;
    days?: string | null;
}

export async function getGroupedBeers(options: GetGroupedBeersOptions) {
    const {
        search, sort, page, limit, shop,
        min_abv, max_abv, min_ibu, max_ibu, min_rating,
        style_filter, stock_filter, product_type, brewery_filter, days
    } = options;

    const offset = (page - 1) * limit;

    const buildQuery = () => {
        let q = supabase
            .from('beer_groups_view')
            .select('*', { count: 'exact' });

        if (days) {
            const daysNum = parseInt(days, 10);
            if (!isNaN(daysNum) && daysNum > 0) {
                const thresholdDate = new Date();
                thresholdDate.setDate(thresholdDate.getDate() - daysNum);
                q = q.gte('newest_seen', thresholdDate.toISOString());
            }
        }

        if (search) {
            q = q.or(`beer_name.ilike.%${search}%,brewery_name.ilike.%${search}%`);
        }

        if (min_abv) q = q.gte('abv', min_abv);
        if (max_abv) q = q.lte('abv', max_abv);
        if (min_ibu) q = q.gte('ibu', min_ibu);
        if (max_ibu) q = q.lte('ibu', max_ibu);
        if (min_rating) q = q.gte('rating', min_rating);

        if (style_filter) {
            const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean);
            if (styles.length > 0) q = q.in('style', styles);
        }

        if (brewery_filter) {
            const breweries = brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean);
            if (breweries.length > 0) q = q.in('brewery_name', breweries);
        }

        if (shop) {
            const shops = shop.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean);
            if (shops.length > 0) {
                const orFilters = shops.map(s => `items.cs.[{"shop":"${s}"}]`).join(',');
                q = q.or(orFilters);
            }
        }

        if (stock_filter === 'in_stock') {
            q = q.contains('items', [{ stock_status: 'In Stock' }]);
        } else if (stock_filter === 'sold_out') {
            q = q.not('items', 'cs', '[{"stock_status":"In Stock"}]');
        }

        if (product_type) {
            q = q.eq('product_type', product_type);
        }

        switch (sort) {
            case 'newest':
                q = q.order('newest_seen', { ascending: false, nullsFirst: false });
                break;
            case 'price_asc':
                q = q.order('min_price', { ascending: true, nullsFirst: false });
                break;
            case 'price_desc':
                q = q.order('max_price', { ascending: false, nullsFirst: false });
                break;
            case 'abv_desc':
                q = q.order('abv', { ascending: false, nullsFirst: false });
                break;
            case 'rating_desc':
                q = q.order('rating', { ascending: false, nullsFirst: false });
                break;
            case 'name_asc':
                q = q.order('beer_name', { ascending: true });
                break;
            default:
                q = q.order('newest_seen', { ascending: false, nullsFirst: false });
        }

        return q;
    };

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
            p_product_type: product_type || null
        });
    };

    let groupsData: any[] = [];
    let totalCount = 0;
    let countRes: any = { data: [] };

    try {
        const [dataRes, fetchedCounts] = await Promise.all([
            buildQuery().range(offset, offset + limit - 1),
            fetchShopCounts()
        ]);
        
        countRes = fetchedCounts;

        if (dataRes.error) {
            if (dataRes.error.code === '42883') {
                console.warn("⚠️ Database view returns 'json' instead of 'jsonb'. Falling back to in-memory filtering for shop/stock...");
                
                const buildFallbackQuery = () => {
                    let q = supabase
                        .from('beer_groups_view')
                        .select('*');

                    if (search) {
                        q = q.or(`beer_name.ilike.%${search}%,brewery_name.ilike.%${search}%`);
                    }
                    if (min_abv) q = q.gte('abv', min_abv);
                    if (max_abv) q = q.lte('abv', max_abv);
                    if (min_ibu) q = q.gte('ibu', min_ibu);
                    if (max_ibu) q = q.lte('ibu', max_ibu);
                    if (min_rating) q = q.gte('rating', min_rating);
                    if (style_filter) {
                        const styles = style_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean);
                        if (styles.length > 0) q = q.in('style', styles);
                    }
                    if (brewery_filter) {
                        const breweries = brewery_filter.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean);
                        if (breweries.length > 0) q = q.in('brewery_name', breweries);
                    }
                    if (product_type) {
                        q = q.eq('product_type', product_type);
                    }

                    switch (sort) {
                        case 'newest':
                            q = q.order('newest_seen', { ascending: false, nullsFirst: false });
                            break;
                        case 'price_asc':
                            q = q.order('min_price', { ascending: true, nullsFirst: false });
                            break;
                        case 'price_desc':
                            q = q.order('max_price', { ascending: false, nullsFirst: false });
                            break;
                        case 'abv_desc':
                            q = q.order('abv', { ascending: false, nullsFirst: false });
                            break;
                        case 'rating_desc':
                            q = q.order('rating', { ascending: false, nullsFirst: false });
                            break;
                        case 'name_asc':
                            q = q.order('beer_name', { ascending: true });
                            break;
                        default:
                            q = q.order('newest_seen', { ascending: false, nullsFirst: false });
                    }
                    return q;
                };

                const fallbackRes = await buildFallbackQuery().limit(2000);
                if (fallbackRes.error) throw fallbackRes.error;

                let allGroups = fallbackRes.data || [];

                if (shop) {
                    const shops = shop.normalize('NFC').split(',').map(s => s.trim()).filter(Boolean);
                    if (shops.length > 0) {
                        allGroups = allGroups.filter(g => {
                            const items = (g.items as any[]) || [];
                            return items.some(item => shops.includes(item.shop));
                        });
                    }
                }

                if (stock_filter === 'in_stock') {
                    allGroups = allGroups.filter(g => {
                        const items = (g.items as any[]) || [];
                        return items.some(item => item.stock_status === 'In Stock');
                    });
                } else if (stock_filter === 'sold_out') {
                    allGroups = allGroups.filter(g => {
                        const items = (g.items as any[]) || [];
                        return !items.some(item => item.stock_status === 'In Stock');
                    });
                }

                totalCount = allGroups.length;
                groupsData = allGroups.slice(offset, offset + limit - 1);
            } else {
                throw dataRes.error;
            }
        } else {
            groupsData = dataRes.data || [];
            totalCount = dataRes.count || 0;
        }
    } catch (dbError) {
        console.error("DB query execution failed:", dbError);
        throw dbError;
    }

    const shopCounts: Record<string, number> = {};
    if (countRes.data) {
        countRes.data.forEach((item: any) => {
            shopCounts[item.shop] = Number(item.shop_count);
        });
    }

    return {
        groupsData,
        shopCounts,
        totalCount
    };
}

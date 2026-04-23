import { GetServerSideProps } from 'next'
import Head from 'next/head'
import React, { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import GroupedBeerTable from '../components/GroupedBeerTable'
import Pagination from '../components/Pagination'
import BeerFilters from '../components/BeerFilters'
import { supabase } from '../lib/supabase'
import type { GroupedBeer, FilterState, BreweryOption, StyleOption, GroupedBeersApiResponse } from '../types/beer'

interface GroupedProps {
    initialData: GroupedBeersApiResponse;
    availableStyles: (string | StyleOption)[];
    availableBreweries: BreweryOption[];
}

export const getServerSideProps: GetServerSideProps = async (context) => {
    const { query } = context;
    
    try {
        const page = (query.page as string) || '1';
        const limit = (query.limit as string) || '20';
        const search = (query.search as string) || '';
        const sort = (query.sort as string) || 'newest';
        
        const pageNum = parseInt(page, 10);
        const limitNum = parseInt(limit, 10);
        const offset = (pageNum - 1) * limitNum;

        // Use beer_groups_view for SQL-level grouping and sorting
        let q = supabase.from('beer_groups_view').select('*', { count: 'exact' });

        if (search) q = q.or(`beer_name.ilike.%${search}%,brewery_name.ilike.%${search}%`);
        if (query.min_abv) q = q.gte('abv', query.min_abv);
        if (query.max_abv) q = q.lte('abv', query.max_abv);
        if (query.min_rating) q = q.gte('rating', query.min_rating as string);
        if (query.style_filter) {
            const styles = (query.style_filter as string).split(',').filter(Boolean);
            if (styles.length > 0) q = q.in('style', styles);
        }
        if (query.brewery_filter) {
            const breweries = (query.brewery_filter as string).split(',').filter(Boolean);
            if (breweries.length > 0) q = q.in('brewery_name', breweries);
        }

        switch (sort) {
            case 'newest': q = q.order('newest_seen', { ascending: false }); break;
            case 'price_asc': q = q.order('min_price', { ascending: true }); break;
            case 'price_desc': q = q.order('max_price', { ascending: false }); break;
            case 'rating_desc': q = q.order('rating', { ascending: false }); break;
            default: q = q.order('newest_seen', { ascending: false });
        }

        const { data: groups, count, error: dataError } = await q.range(offset, offset + limitNum - 1);
        if (dataError) throw dataError;

        // Optimized aggregation via RPC
        const { data: filterData, error: rpcError } = await supabase.rpc('get_available_filters').single();
        if (rpcError) console.error('RPC Error in getServerSideProps (Grouped):', rpcError);
        
        const typedFilterData = filterData as any;
        const styles = typedFilterData?.styles || [];
        const breweries = typedFilterData?.breweries?.map((b: any) => ({
            name: b.name_en || b.name_jp || 'Unknown',
            flag: ''
        })) || [];

        return {
            props: {
                initialData: {
                    groups: groups || [],
                    shopCounts: {},
                    pagination: {
                        page: pageNum,
                        limit: limitNum,
                        total: count || 0,
                        totalPages: Math.ceil((count || 0) / limitNum)
                    }
                },
                availableStyles: styles,
                availableBreweries: breweries
            }
        }
    } catch (err) {
        console.error('getServerSideProps error in GroupedBeers:', err);
        return {
            props: {
                initialData: {
                    groups: [],
                    shopCounts: {},
                    pagination: { page: 1, limit: 20, total: 0, totalPages: 0 }
                },
                availableStyles: [],
                availableBreweries: []
            }
        }
    }
}

export default function GroupedBeers({ initialData, availableStyles, availableBreweries }: GroupedProps) {
    const router = useRouter()
    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)

    const [groups, setGroups] = useState<GroupedBeer[]>(initialData.groups)
    const [shopCounts, setShopCounts] = useState<Record<string, number>>(initialData.shopCounts)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [totalPages, setTotalPages] = useState(initialData.pagination.totalPages)
    const [totalItems, setTotalItems] = useState(initialData.pagination.total)

    const [searchInput, setSearchInput] = useState((router.query.search as string) || '')
    const [isFilterOpen, setIsFilterOpen] = useState(false)
    
    const [tempFilters, setTempFilters] = useState<FilterState>({
        min_abv: (router.query.min_abv as string) || '', 
        max_abv: (router.query.max_abv as string) || '', 
        min_ibu: (router.query.min_ibu as string) || '', 
        max_ibu: (router.query.max_ibu as string) || '', 
        min_rating: (router.query.min_rating as string) || '',
        stock_filter: (router.query.stock_filter as string) || 'in_stock', 
        untappd_status: (router.query.untappd_status as string) || '', 
        shop: (router.query.shop as string) || '',
        brewery_filter: (router.query.brewery_filter as string) || '', 
        style_filter: (router.query.style_filter as string) || '', 
        set_mode: (router.query.set_mode as string) || ''
    })

    const filterTimeoutRef = useRef<NodeJS.Timeout | null>(null)

    const page = parseInt((router.query.page as string) || '1', 10)
    const limit = (router.query.limit as string) || '20'
    const sort = (router.query.sort as string) || 'newest'

    useEffect(() => {
        setGroups(initialData.groups);
        setTotalPages(initialData.pagination.totalPages);
        setTotalItems(initialData.pagination.total);
        setShopCounts(initialData.shopCounts);
        setSearchInput((router.query.search as string) || '');
        setTempFilters({
            min_abv: (router.query.min_abv as string) || '',
            max_abv: (router.query.max_abv as string) || '',
            min_ibu: (router.query.min_ibu as string) || '',
            max_ibu: (router.query.max_ibu as string) || '',
            min_rating: (router.query.min_rating as string) || '',
            stock_filter: (router.query.stock_filter as string) || 'in_stock',
            untappd_status: (router.query.untappd_status as string) || '',
            shop: (router.query.shop as string) || '',
            brewery_filter: (router.query.brewery_filter as string) || '',
            style_filter: (router.query.style_filter as string) || '',
            set_mode: (router.query.set_mode as string) || ''
        });
    }, [initialData, router.query]);

    const fetchGroups = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams(router.query as any);
            const res = await fetch(`/api/grouped-beers?${params}`);
            const data: GroupedBeersApiResponse = await res.json();
            setGroups(data.groups || []);
            setShopCounts(data.shopCounts || {});
            setTotalPages(data.pagination.totalPages);
            setTotalItems(data.pagination.total);
        } catch (err) {
            setError('Refresh failed');
        } finally {
            setLoading(false);
        }
    }, [router.query]);

    const updateURL = (newParams: Record<string, string>, pathname = '/grouped') => {
        const query = { ...router.query, ...newParams }
        if (query.page == '1') delete query.page
        if (query.limit == '20') delete query.limit
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        router.push({ pathname, query }, undefined, { scroll: false, shallow: false })
    }

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value
        setSearchInput(val)
        if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
        searchTimeoutRef.current = setTimeout(() => updateURL({ search: val, page: '1' }), 500)
    }

    const handleFilterChange = (key: string, value: string) => {
        setTempFilters(prev => ({ ...prev, [key]: value }));
        if (filterTimeoutRef.current) clearTimeout(filterTimeoutRef.current);
        filterTimeoutRef.current = setTimeout(() => {
            updateURL({ [key]: value, page: '1' });
        }, 500);
    }
    const handleMultiSelectChange = (key: string, value: string[]) => updateURL({ [key]: value.join(','), page: '1' })
    const resetFilters = () => router.push({ pathname: '/grouped', query: {} }, undefined, { scroll: false })
    const handlePageChange = (newPage: number) => updateURL({ page: newPage.toString() })

    return (
        <>
            <Head>
                <meta charSet="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Grouped Beers - Craft Beer Alert Japan</title>
                <meta name="description" content="Compare prices and find where to buy your favorite craft beers." />
            </Head>

            <header className="glass-header">
                <div className="container header-content">
                    <h1>
                        <Link href="/" onClick={resetFilters} style={{ textDecoration: 'none', color: 'inherit' }}>
                            Craft Beer Alert Japan
                        </Link>
                    </h1>
                    <div className="search-bar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                        <input
                            type="text"
                            placeholder="Search beers..."
                            value={searchInput}
                            onChange={handleSearchChange}
                            aria-label="Search for beers"
                        />
                    </div>
                </div>
            </header>

            <main className="container" style={{ minHeight: '80vh' }}>
                <BeerFilters
                    shop={(router.query.shop as string) || ''}
                    shopCounts={shopCounts}
                    brewery_filter={(router.query.brewery_filter as string) || ''}
                    style_filter={(router.query.style_filter as string) || ''}
                    sort={sort}
                    limit={limit}
                    isFilterOpen={isFilterOpen}
                    activeFilterCount={Object.keys(router.query).length}
                    tempFilters={tempFilters}
                    availableBreweries={availableBreweries}
                    availableStyles={availableStyles}
                    onMultiSelectChange={handleMultiSelectChange}
                    onSortChange={(e) => updateURL({ sort: e.target.value, page: '1' })}
                    onLimitChange={(e) => updateURL({ limit: e.target.value, page: '1' })}
                    onToggleFilter={() => setIsFilterOpen(!isFilterOpen)}
                    onReset={resetFilters}
                    onFilterChange={handleFilterChange}
                    viewMode="grouped"
                    onViewModeChange={(mode) => mode === 'individual' && router.push('/')}
                    onRefresh={fetchGroups}
                />

                <GroupedBeerTable
                    groups={groups}
                    loading={loading}
                    error={error}
                />

                {!loading && !error && (
                    <Pagination
                        currentPage={page}
                        totalPages={totalPages}
                        totalItems={totalItems}
                        onPageChange={handlePageChange}
                    />
                )}
            </main>

            <footer className="glass-footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Watch Japan.</p>
                </div>
            </footer>
        </>
    )
}

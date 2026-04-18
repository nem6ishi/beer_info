import { GetServerSideProps } from 'next'
import Head from 'next/head'
import React, { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import BeerTable from '../components/BeerTable'
import Pagination from '../components/Pagination'
import BeerFilters from '../components/BeerFilters'
import { supabase } from '../lib/supabase'
import type { Beer, FilterState, BreweryOption, StyleOption, BeersApiResponse } from '../types/beer'

interface HomeProps {
    initialData: BeersApiResponse;
    availableStyles: (string | StyleOption)[];
    availableBreweries: BreweryOption[];
}

export const getServerSideProps: GetServerSideProps = async (context) => {
    const { query } = context;
    
    // Construct the absolute URL for the internal API call
    // Since we are on Vercel or local, we can use the relative URL trick or call the local handler directly.
    // However, it's cleaner to reuse the logic. For now, we'll fetch styles and breweries from Supabase directly here 
    // to avoid an extra internal HTTP hop, or just use the API logic.
    
    const page = (query.page as string) || '1';
    const limit = (query.limit as string) || '20';
    const search = (query.search as string) || '';
    const sort = (query.sort as string) || 'newest';
    const shop = (query.shop as string) || '';
    
    // We'll mimic the /api/beers logic here for the initial fetch
    const pageNum = parseInt(page, 10);
    const limitNum = parseInt(limit, 10);
    const offset = (pageNum - 1) * limitNum;

    let q = supabase.from('beer_info_view').select('*', { count: 'exact' });

    if (search) q = q.or(`name.ilike.%${search}%,beer_name_en.ilike.%${search}%,brewery_name_en.ilike.%${search}%,untappd_brewery_name.ilike.%${search}%`);
    if (query.min_abv) q = q.gte('untappd_abv', query.min_abv);
    if (query.max_abv) q = q.lte('untappd_abv', query.max_abv);
    if (query.min_rating) q = q.gte('untappd_rating', query.min_rating);
    if (shop) q = q.in('shop', shop.split(','));
    if (query.style_filter) q = q.in('untappd_style', (query.style_filter as string).split(','));
    if (query.brewery_filter) q = q.in('untappd_brewery_name', (query.brewery_filter as string).split(','));
    
    if (query.stock_filter === 'in_stock') q = q.eq('stock_status', 'In Stock');
    else if (query.stock_filter === 'sold_out') q = q.eq('stock_status', 'Sold Out');

    switch (sort) {
        case 'newest': q = q.order('first_seen', { ascending: false }); break;
        case 'price_asc': q = q.order('price_value', { ascending: true }); break;
        case 'price_desc': q = q.order('price_value', { ascending: false }); break;
        case 'rating_desc': q = q.order('untappd_rating', { ascending: false }); break;
        default: q = q.order('first_seen', { ascending: false });
    }

    const { data: beers, count } = await q.range(offset, offset + limitNum - 1);

    // Fetch styles and breweries
    const [stylesRes, breweriesRes] = await Promise.all([
        supabase.from('beer_info_view').select('untappd_style').not('untappd_style', 'is', null),
        supabase.from('breweries').select('name_en, name_jp').order('name_en')
    ]);

    // Simple style counting
    const styleMap: Record<string, number> = {};
    stylesRes.data?.forEach(item => {
        if (item.untappd_style) styleMap[item.untappd_style] = (styleMap[item.untappd_style] || 0) + 1;
    });
    const styles = Object.entries(styleMap).map(([style, count]) => ({ style, count })).sort((a, b) => b.count - a.count);

    const breweries = breweriesRes.data?.map(b => ({
        name: b.name_en || b.name_jp,
        flag: '' // Optional
    })) || [];

    return {
        props: {
            initialData: {
                beers: beers || [],
                shopCounts: {}, // Can be calculated if needed
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
}

export default function Home({ initialData, availableStyles, availableBreweries }: HomeProps) {
    const router = useRouter()

    // State initialized from Props
    const [beers, setBeers] = useState<Beer[]>(initialData.beers)
    const [shopCounts, setShopCounts] = useState<Record<string, number>>(initialData.shopCounts)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [totalPages, setTotalPages] = useState(initialData.pagination.totalPages)
    const [totalItems, setTotalItems] = useState(initialData.pagination.total)
    
    const [searchInput, setSearchInput] = useState('')
    const [isFilterOpen, setIsFilterOpen] = useState(false)
    
    const [tempFilters, setTempFilters] = useState<FilterState>({
        min_abv: '', max_abv: '', min_ibu: '', max_ibu: '', min_rating: '',
        stock_filter: 'in_stock', untappd_status: '', shop: '',
        brewery_filter: '', style_filter: '', set_mode: ''
    })

    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const page = parseInt((router.query.page as string) || '1', 10)
    const sort = (router.query.sort as string) || 'newest'
    const limit = (router.query.limit as string) || '20'

    // Update local state when initialData changes (client-side navigation)
    useEffect(() => {
        setBeers(initialData.beers);
        setTotalPages(initialData.pagination.totalPages);
        setTotalItems(initialData.pagination.total);
        setShopCounts(initialData.shopCounts);
        setSearchInput((router.query.search as string) || '');
    }, [initialData]);

    const fetchBeers = useCallback(async () => {
        // This is now only for explicit refresh action
        setLoading(true);
        try {
            const params = new URLSearchParams(router.query as any);
            const res = await fetch(`/api/beers?${params}`);
            const data: BeersApiResponse = await res.json();
            setBeers(data.beers || []);
            setShopCounts(data.shopCounts || {});
            setTotalPages(data.pagination.totalPages);
            setTotalItems(data.pagination.total);
        } catch (err) {
            setError('Refresh failed');
        } finally {
            setLoading(false);
        }
    }, [router.query]);

    const updateURL = (newParams: Record<string, string>, pathname = '/') => {
        const query = { ...router.query, ...newParams }
        // Cleanups
        if (query.page == '1') delete query.page
        if (query.limit == '20') delete query.limit
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        if (!query.shop) delete query.shop
        if (query.stock_filter === 'in_stock') delete query.stock_filter
        
        router.push({ pathname, query }, undefined, { scroll: false, shallow: false }) // Use shallow=false to trigger getServerSideProps
    }

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value
        setSearchInput(val)
        if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
        searchTimeoutRef.current = setTimeout(() => updateURL({ search: val, page: '1' }), 500)
    }

    const handleFilterChange = (key: string, value: string) => updateURL({ [key]: value, page: '1' })
    const handleMultiSelectChange = (key: string, value: string[]) => updateURL({ [key]: value.join(','), page: '1' })
    const resetFilters = () => router.push({ pathname: '/', query: {} }, undefined, { scroll: false })
    const handlePageChange = (newPage: number) => updateURL({ page: newPage.toString() })

    return (
        <>
            <Head>
                <meta charSet="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Craft Beer Alert Japan</title>
                <meta name="description" content="Discover premium craft beers collected from the best Japanese shops." />
            </Head>

            <header className="glass-header">
                <div className="container header-content">
                    <h1>
                        <Link href="/" onClick={resetFilters} style={{ textDecoration: 'none', color: 'inherit' }}>
                            Craft Beer Alert Japan
                        </Link>
                    </h1>
                    <div className="search-bar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: '#999', zIndex: 2 }}>
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
                    onViewModeChange={(mode) => mode === 'grouped' && router.push('/grouped')}
                    onRefresh={fetchBeers}
                />

                <BeerTable beers={beers} loading={loading} error={error} />

                {!loading && !error && (
                    <Pagination
                        currentPage={page}
                        totalPages={totalPages}
                        totalItems={totalItems}
                        onPageChange={handlePageChange}
                    />
                )}
            </main>

            <footer className="footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Watch Japan.</p>
                </div>
            </footer>
        </>
    )
}

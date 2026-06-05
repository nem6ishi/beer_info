"use client";

import React, { useState, useEffect, useCallback, useRef, useTransition } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import BeerTable from './BeerTable'
import Pagination from './Pagination'
import BeerFilters from './BeerFilters'
import type { Beer, FilterState, BreweryOption, StyleOption, BeersApiResponse } from '../types/beer'

interface HomeClientProps {
    initialData: BeersApiResponse;
    availableStyles: (string | StyleOption)[];
    availableBreweries: BreweryOption[];
}

export default function HomeClient({ initialData, availableStyles, availableBreweries }: HomeClientProps) {
    const router = useRouter()
    const searchParams = useSearchParams()
    const pathname = usePathname()

    const [beers, setBeers] = useState<Beer[]>(initialData.beers)
    const [shopCounts, setShopCounts] = useState<Record<string, number>>(initialData.shopCounts)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [totalPages, setTotalPages] = useState(initialData.pagination.totalPages)
    const [totalItems, setTotalItems] = useState(initialData.pagination.total)
    const [isPending, startTransition] = useTransition()
    
    const searchParamStr = searchParams.get('search') || '';
    const [searchInput, setSearchInput] = useState(searchParamStr)
    const [isFilterOpen, setIsFilterOpen] = useState(false)
    
    const [tempFilters, setTempFilters] = useState<FilterState>({
        min_abv: searchParams.get('min_abv') || '', 
        max_abv: searchParams.get('max_abv') || '', 
        min_ibu: searchParams.get('min_ibu') || '', 
        max_ibu: searchParams.get('max_ibu') || '', 
        min_rating: searchParams.get('min_rating') || '',
        stock_filter: searchParams.get('stock_filter') || 'in_stock', 
        untappd_status: searchParams.get('untappd_status') || '', 
        shop: searchParams.get('shop') || '',
        brewery_filter: searchParams.get('brewery_filter') || '', 
        style_filter: searchParams.get('style_filter') || '', 
        set_mode: searchParams.get('set_mode') || '',
        debug: searchParams.get('debug') || ''
    })

    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const filterTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const abortControllerRef = useRef<AbortController | null>(null)
    const page = parseInt(searchParams.get('page') || '1', 10)
    const sort = searchParams.get('sort') || 'newest'
    const limit = searchParams.get('limit') || '20'

    const fetchBeers = useCallback(async () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        const controller = new AbortController();
        abortControllerRef.current = controller;

        setLoading(true);
        try {
            const params = new URLSearchParams(searchParams.toString());
            const res = await fetch(`/api/beers?${params.toString()}`, { signal: controller.signal });
            const data: BeersApiResponse = await res.json();
            setBeers(data.beers || []);
            setShopCounts(data.shopCounts || {});
            setTotalPages(data.pagination.totalPages);
            setTotalItems(data.pagination.total);
            setError(null);
        } catch (err: any) {
            if (err.name !== 'AbortError') {
                setError('Refresh failed');
            }
        } finally {
            if (abortControllerRef.current === controller) {
                setLoading(false);
            }
        }
    }, [searchParams]);

    useEffect(() => {
        const hasFilters = Array.from(searchParams.keys()).length > 0;
        
        if (hasFilters) {
            // URL has parameters, fetch client-side
            fetchBeers();
        } else {
            // No parameters, use the instantly loaded static default data
            setBeers(initialData.beers);
            setTotalPages(initialData.pagination.totalPages);
            setTotalItems(initialData.pagination.total);
            setShopCounts(initialData.shopCounts);
        }
        
        setSearchInput(searchParams.get('search') || '');
        setTempFilters({
            min_abv: searchParams.get('min_abv') || '',
            max_abv: searchParams.get('max_abv') || '',
            min_ibu: searchParams.get('min_ibu') || '',
            max_ibu: searchParams.get('max_ibu') || '',
            min_rating: searchParams.get('min_rating') || '',
            stock_filter: searchParams.get('stock_filter') || 'in_stock',
            untappd_status: searchParams.get('untappd_status') || '',
            shop: searchParams.get('shop') || '',
            brewery_filter: searchParams.get('brewery_filter') || '',
            style_filter: searchParams.get('style_filter') || '',
            set_mode: searchParams.get('set_mode') || '',
            debug: searchParams.get('debug') || ''
        });
    }, [initialData, searchParams, fetchBeers]);

    const updateURL = (newParams: Record<string, string>, targetPath = pathname) => {
        const params = new URLSearchParams(searchParams.toString());
        
        Object.entries(newParams).forEach(([key, value]) => {
            if (value === '') {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        });

        if (params.get('page') === '1') params.delete('page');
        if (params.get('limit') === '20') params.delete('limit');
        if (params.get('sort') === 'newest') params.delete('sort');
        if (!params.get('search')) params.delete('search');
        if (!params.get('shop')) params.delete('shop');
        if (params.get('stock_filter') === 'in_stock') params.delete('stock_filter');

        const searchStr = params.toString();
        const queryStr = searchStr ? `?${searchStr}` : '';
        startTransition(() => {
            router.push(`${targetPath}${queryStr}`, { scroll: false });
        });
    }

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value
        setSearchInput(val)
        if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current)
        searchTimeoutRef.current = setTimeout(() => updateURL({ search: val, page: '1' }), 300)
    }

    const handleFilterChange = (key: string, value: string) => {
        setTempFilters(prev => ({ ...prev, [key]: value }));
        if (filterTimeoutRef.current) clearTimeout(filterTimeoutRef.current);
        filterTimeoutRef.current = setTimeout(() => {
            updateURL({ [key]: value, page: '1' });
        }, 300);
    }
    
    const handleMultiSelectChange = (key: string, value: string[]) => {
        setTempFilters(prev => ({ ...prev, [key]: value.join(',') }));
        updateURL({ [key]: value.join(','), page: '1' });
    }
    const resetFilters = () => {
        startTransition(() => {
            router.push(pathname, { scroll: false });
        });
    }
    const handlePageChange = (newPage: number) => updateURL({ page: newPage.toString() })

    // Build mock router query object for BeerFilters compatibility
    const queryObj: Record<string, string> = {};
    searchParams.forEach((val, key) => { queryObj[key] = val; });

    return (
        <>
            <header className="glass-header">
                <div className="container header-content">
                    <h1>
                        <Link href="/" onClick={(e) => { e.preventDefault(); resetFilters(); }} style={{ textDecoration: 'none', color: 'inherit' }}>
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
                    shop={tempFilters.shop}
                    shopCounts={shopCounts}
                    brewery_filter={tempFilters.brewery_filter}
                    style_filter={tempFilters.style_filter}
                    sort={sort}
                    limit={limit}
                    isFilterOpen={isFilterOpen}
                    activeFilterCount={Array.from(searchParams.keys()).length}
                    tempFilters={tempFilters}
                    availableBreweries={availableBreweries}
                    availableStyles={availableStyles}
                    onMultiSelectChange={handleMultiSelectChange}
                    onSortChange={(e) => updateURL({ sort: e.target.value, page: '1' })}
                    onLimitChange={(e) => updateURL({ limit: e.target.value, page: '1' })}
                    onToggleFilter={() => setIsFilterOpen(!isFilterOpen)}
                    onReset={resetFilters}
                    onFilterChange={handleFilterChange}
                    onViewModeChange={(mode) => mode === 'grouped' && updateURL({}, '/grouped')}
                    onRefresh={fetchBeers}
                />

                <div id="results-top" style={{ scrollMarginTop: '120px' }}></div>
                <BeerTable beers={beers} loading={loading || isPending} error={error} isDebug={searchParams.get('debug') === '1'} />

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

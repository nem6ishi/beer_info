import Head from 'next/head'
import React, { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import GroupedBeerTable from '../components/GroupedBeerTable'
import Pagination from '../components/Pagination'
import BeerFilters from '../components/BeerFilters'
import type { GroupedBeer, FilterState, BreweryOption, StyleOption, GroupedBeersApiResponse } from '../types/beer'

export default function GroupedBeers() {
    const router = useRouter()

    // State for data
    const [groups, setGroups] = useState<GroupedBeer[]>([])
    const [shopCounts, setShopCounts] = useState<Record<string, number>>({})
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [totalPages, setTotalPages] = useState(0)
    const [totalItems, setTotalItems] = useState(0)
    const [mounted, setMounted] = useState(false)
    const [forcedReady, setForcedReady] = useState(false)

    // UI State
    const [searchInput, setSearchInput] = useState('')
    const [isFilterOpen, setIsFilterOpen] = useState(false)
    const [availableStyles, setAvailableStyles] = useState<(string | StyleOption)[]>([])
    const [availableBreweries, setAvailableBreweries] = useState<BreweryOption[]>([])

    // Filter UI State
    const [tempFilters, setTempFilters] = useState<FilterState>({
        min_abv: '',
        max_abv: '',
        min_ibu: '',
        max_ibu: '',
        min_rating: '',
        stock_filter: 'in_stock',
        untappd_status: '',
        shop: '',
        brewery_filter: '',
        style_filter: '',
        set_mode: ''
    })

    // Derived state from URL (defaults)
    const page = parseInt((router.query.page as string) || '1', 10)
    const limit = (router.query.limit as string) || '20'
    const sort = (router.query.sort as string) || 'newest'
    const shop = (router.query.shop as string) || ''
    const style_filter = (router.query.style_filter as string) || ''
    const brewery_filter = (router.query.brewery_filter as string) || ''

    // Initialize search input from URL
    useEffect(() => {
        setMounted(true)
        if (router.isReady || forcedReady) {
            setSearchInput((router.query.search as string) || '')
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
            })

            fetch('/api/styles')
                .then(res => res.json())
                .then(data => {
                    if (data.styles) setAvailableStyles(data.styles)
                })
                .catch(err => console.error('Failed to load styles', err))

            fetch('/api/breweries')
                .then(res => res.json())
                .then(data => {
                    if (data.breweries) setAvailableBreweries(data.breweries)
                })
                .catch(err => console.error('Failed to load breweries', err))
        }
    }, [router.isReady, forcedReady, router.query])

    // Safety timeout for router.isReady
    useEffect(() => {
        const timer = setTimeout(() => {
            if (!router.isReady) {
                console.warn("Router not ready after 3s, forcing ready state for Safari/280blocker resilience.");
                setForcedReady(true);
            }
        }, 3000);
        return () => clearTimeout(timer);
    }, [router.isReady]);

    // Data Fetching
    const fetchGroups = useCallback(async () => {
        if (!router.isReady && !forcedReady) return;
        if (!mounted) return;

        setLoading(true);
        setError(null);

        try {
            const currentParams = router.query;
            const params = new URLSearchParams({
                page: (currentParams.page as string) || '1',
                limit: (currentParams.limit as string) || '20',
                search: (currentParams.search as string) || '',
                sort: (currentParams.sort as string) || 'newest',
                stock_filter: (currentParams.stock_filter as string) || 'in_stock'
            });

            if (currentParams.shop) params.append('shop', currentParams.shop as string);

            ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'untappd_status', 'set_mode']
                .forEach(key => { if (currentParams[key]) params.append(key, currentParams[key] as string) });

            const res = await fetch(`/api/grouped-beers?${params}`);

            if (!res.ok) throw new Error('Failed to load grouped beers');

            const data: GroupedBeersApiResponse = await res.json();
            setGroups(data.groups || []);
            setShopCounts(data.shopCounts || {});
            setTotalPages(data.pagination.totalPages);
            setTotalItems(data.pagination.total);
        } catch (err) {
            console.error('Fetch error:', err);
            setError('Failed to load data. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [router.isReady, router.query, mounted, forcedReady]);

    // Fetch on URL change
    useEffect(() => {
        fetchGroups();
    }, [fetchGroups]);

    // Helper to update URL
    const updateURL = (newParams: Record<string, string>, pathname = '/grouped') => {
        const query = { ...router.query, ...newParams }

        if (query.page == '1') delete query.page
        if (query.limit == '20') delete query.limit
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        if (!query.shop) delete query.shop
        if (query.stock_filter === 'in_stock') delete query.stock_filter
        
        const filterKeys = ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'untappd_status', 'set_mode']
        filterKeys.forEach(key => {
            if (!query[key]) delete query[key]
        })

        router.push({ pathname, query }, undefined, { scroll: false })
    }

    // Filter Logic
    const activeFilterCount = (() => {
        if (!router.isReady && !forcedReady) return 0
        const keys = ['min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'shop', 'style_filter', 'brewery_filter', 'untappd_status', 'set_mode']
        return keys.filter(k => !!router.query[k]).length
    })()

    const handleFilterChange = (key: string, value: string) => {
        setTempFilters(prev => ({ ...prev, [key]: value }))
        if (key === 'stock_filter' || key === 'untappd_status') {
            updateURL({ [key]: value, page: '1' })
        }
    }

    // Debounced effect for Advanced Filters
    useEffect(() => {
        if (!router.isReady && !forcedReady) return

        const timeoutId = setTimeout(() => {
            const query = router.query
            const { min_abv, max_abv, min_ibu, max_ibu, min_rating } = tempFilters

            if (
                min_abv !== ((query.min_abv as string) || '') ||
                max_abv !== ((query.max_abv as string) || '') ||
                min_ibu !== ((query.min_ibu as string) || '') ||
                max_ibu !== ((query.max_ibu as string) || '') ||
                min_rating !== ((query.min_rating as string) || '')
            ) {
                updateURL({ ...tempFilters, page: '1' })
            }

        }, 500)

        return () => clearTimeout(timeoutId)
    }, [tempFilters, router.isReady, forcedReady]);

    const handleMultiSelectChange = (paramKey: string, newValues: string[]) => {
        const valueStr = newValues.join(',')
        updateURL({ [paramKey]: valueStr, page: '1' })
    }

    const resetFilters = () => {
        const resetState: FilterState = {
            min_abv: '',
            max_abv: '',
            min_ibu: '',
            max_ibu: '',
            min_rating: '',
            stock_filter: 'in_stock',
            untappd_status: '',
            shop: '',
            brewery_filter: '',
            style_filter: '',
            set_mode: ''
        }
        setTempFilters(resetState)
        setSearchInput('')

        router.push({ pathname: '/grouped', query: {} }, undefined, { scroll: false })
    }

    const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setSearchInput(e.target.value)
    }

    // Debounce search update to URL
    useEffect(() => {
        if (!router.isReady && !forcedReady) return

        const currentUrlSearch = (router.query.search as string) || ''
        if (searchInput === currentUrlSearch) return

        const timeoutId = setTimeout(() => {
            updateURL({ search: searchInput, page: '1' })
        }, 500)

        return () => clearTimeout(timeoutId)
    }, [searchInput, router.isReady, forcedReady])


    const handleSort = (e: React.ChangeEvent<HTMLSelectElement>) => {
        updateURL({ sort: e.target.value, page: '1' })
    }

    const handleLimitChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        updateURL({ limit: e.target.value, page: '1' })
    }

    const handlePageChange = (newPage: number) => {
        if (newPage >= 1 && newPage <= totalPages) {
            updateURL({ page: newPage.toString() })
            window.scrollTo({ top: 0, behavior: 'smooth' })
        }
    }

    const handleViewModeChange = (mode: string) => {
        if (mode === 'individual') {
            router.push({ pathname: '/', query: router.query }, undefined, { scroll: false })
        }
    }

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
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                            strokeLinecap="round" strokeLinejoin="round">
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
                        {searchInput && (
                            <button
                                className="clear-search-btn"
                                onClick={() => setSearchInput('')}
                                aria-label="Clear search"
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <line x1="18" y1="6" x2="6" y2="18"></line>
                                    <line x1="6" y1="6" x2="18" y2="18"></line>
                                </svg>
                            </button>
                        )}
                    </div>
                </div>
            </header>

            <main className="container">

                <BeerFilters
                    shop={shop}
                    shopCounts={shopCounts}
                    brewery_filter={brewery_filter}
                    style_filter={style_filter}
                    sort={sort}
                    limit={limit}
                    isFilterOpen={isFilterOpen}
                    activeFilterCount={activeFilterCount}
                    tempFilters={tempFilters}
                    availableBreweries={availableBreweries}
                    availableStyles={availableStyles}
                    onMultiSelectChange={handleMultiSelectChange}
                    onSortChange={handleSort}
                    onLimitChange={handleLimitChange}
                    onToggleFilter={() => setIsFilterOpen(!isFilterOpen)}
                    onReset={resetFilters}
                    onFilterChange={handleFilterChange}
                    viewMode="grouped"
                    onViewModeChange={handleViewModeChange}
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
            </main >

            <footer className="glass-footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Watch Japan. Data sourced from Beervolta &amp; Chouseiya.</p>
                </div>
            </footer>
        </>
    )
}

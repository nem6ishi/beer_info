import Head from 'next/head'
import React, { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import GroupedBeerTable from '../components/GroupedBeerTable'
import Pagination from '../components/Pagination'
import BeerFilters from '../components/BeerFilters'

export default function GroupedBeers() {
    const router = useRouter()

    // State for data
    const [groups, setGroups] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [totalPages, setTotalPages] = useState(0)
    const [totalItems, setTotalItems] = useState(0)

    // UI State
    const [searchInput, setSearchInput] = useState('')
    const [isFilterOpen, setIsFilterOpen] = useState(false)
    const [availableStyles, setAvailableStyles] = useState([]) // Fetched from API
    const [availableBreweries, setAvailableBreweries] = useState([]) // Fetched from API

    // Filter UI State (ABV, IBU, Rating, Stock)
    const [tempFilters, setTempFilters] = useState({
        min_abv: '',
        max_abv: '',
        min_ibu: '',
        max_ibu: '',
        min_rating: '',
        min_rating: '',
        stock_filter: '',
        set_mode: ''
    })

    // Derived state from URL (defaults)
    const page = parseInt(router.query.page || '1', 10)
    const limit = router.query.limit || '20' // Default limit 20
    const sort = router.query.sort || 'newest'
    const shop = router.query.shop || ''
    const style_filter = router.query.style_filter || ''
    const brewery_filter = router.query.brewery_filter || ''

    // Initialize search input from URL once router is ready. 
    useEffect(() => {
        if (router.isReady) {
            setSearchInput(router.query.search || '')
            // Don't need styleInput state anymore, using router directly for multi-select
            setTempFilters({
                min_abv: router.query.min_abv || '',
                max_abv: router.query.max_abv || '',
                min_ibu: router.query.min_ibu || '',
                max_ibu: router.query.max_ibu || '',
                min_rating: router.query.min_rating || '',
                stock_filter: router.query.stock_filter || '',
                stock_filter: router.query.stock_filter || '',
                missing_untappd: router.query.missing_untappd || '',
                set_mode: router.query.set_mode || ''
            })

            // Fetch styles
            fetch('/api/styles')
                .then(res => res.json())
                .then(data => {
                    if (data.styles) setAvailableStyles(data.styles)
                })
                .catch(err => console.error('Failed to load styles', err))

            // Fetch breweries
            fetch('/api/breweries')
                .then(res => res.json())
                .then(data => {
                    if (data.breweries) setAvailableBreweries(data.breweries)
                })
                .catch(err => console.error('Failed to load breweries', err))
        }
    }, [router.isReady])

    // Data Fetching
    // Data Fetching
    const fetchGroups = useCallback(async () => {
        if (!router.isReady) return;

        setLoading(true);
        setError(null);

        try {
            const currentParams = router.query;
            const params = new URLSearchParams({
                page: currentParams.page || '1',
                limit: currentParams.limit || '20',
                search: currentParams.search || '',
                sort: currentParams.sort || 'newest',
            });

            if (currentParams.shop) params.append('shop', currentParams.shop);

            // Add filters
            ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'missing_untappd', 'set_mode']
                .forEach(key => { if (currentParams[key]) params.append(key, currentParams[key]) });

            const res = await fetch(`/api/grouped-beers?${params}`);

            if (!res.ok) throw new Error('Failed to load grouped beers');

            const data = await res.json();
            setGroups(data.groups || []);
            setTotalPages(data.pagination.totalPages);
            setTotalItems(data.pagination.total);
        } catch (err) {
            console.error('Fetch error:', err);
            setError('Failed to load data. Please try again.');
        } finally {
            setLoading(false);
        }
    }, [router.isReady, router.query]);

    // Fetch on URL change
    useEffect(() => {
        fetchGroups();
    }, [fetchGroups]);

    // Helper to update URL
    const updateURL = (newParams, pathname = '/grouped') => {
        const query = { ...router.query, ...newParams }

        // Cleanup defaults to keep URL clean
        if (query.page == '1') delete query.page
        if (query.limit == '20') delete query.limit // Default limit cleanup
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        if (!query.shop) delete query.shop
        // Clean up empty filters
        const filterKeys = ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'missing_untappd', 'set_mode']
        filterKeys.forEach(key => {
            if (!query[key]) delete query[key]
        })

        router.push({ pathname, query }, undefined, { scroll: false })
    }

    // Filter Logic
    const activeFilterCount = (() => {
        if (!router.isReady) return 0
        const keys = ['limit', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'shop', 'style_filter', 'brewery_filter', 'missing_untappd', 'set_mode'] // Limit acts like a filter param
        return keys.filter(k => !!router.query[k] && k !== 'limit' && k !== 'sort' && k !== 'page').length // Exclude structural params from badge count
    })()

    // We update tempFilters state immediately for UI 
    const handleFilterChange = (key, value) => {
        setTempFilters(prev => ({ ...prev, [key]: value }))

        // If it's a select or checkbox (Stock, Missing Untappd), update URL immediately
        if (key === 'stock_filter' || key === 'missing_untappd') {
            updateURL({ [key]: value, page: '1' })
        }
    }

    // Debounced effect for Advanced Filters (ABV, IBU, Rating)
    useEffect(() => {
        if (!router.isReady) return

        const timeoutId = setTimeout(() => {
            const query = router.query
            const { min_abv, max_abv, min_ibu, max_ibu, min_rating } = tempFilters

            if (
                min_abv !== (query.min_abv || '') ||
                max_abv !== (query.max_abv || '') ||
                min_ibu !== (query.min_ibu || '') ||
                max_ibu !== (query.max_ibu || '') ||
                min_rating !== (query.min_rating || '')
            ) {
                updateURL({ ...tempFilters, page: '1' })
            }

        }, 500) // 500ms debounce for typing numbers

        return () => clearTimeout(timeoutId)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tempFilters, router.isReady])

    const handleMultiSelectChange = (paramKey, newValues) => {
        const valueStr = newValues.join(',')
        updateURL({ [paramKey]: valueStr, page: '1' })
    }

    const resetFilters = () => {
        const resetState = {
            min_abv: '',
            max_abv: '',
            min_ibu: '',
            max_ibu: '',
            min_rating: '',
            stock_filter: '',
            min_rating: '',
            stock_filter: '',
            missing_untappd: '',
            set_mode: ''
        }
        setTempFilters(resetState)
        setSearchInput('')

        updateURL({
            min_abv: '',
            max_abv: '',
            min_ibu: '',
            max_ibu: '',
            min_rating: '',
            stock_filter: '',
            missing_untappd: '',
            set_mode: '',
            shop: '',
            style_filter: '',
            brewery_filter: '',
            sort: 'newest',
            search: '',
            page: '1'
        })
    }

    const handleSearchChange = (e) => {
        setSearchInput(e.target.value)
    }

    // Debounce search update to URL
    useEffect(() => {
        if (!router.isReady) return

        const currentUrlSearch = router.query.search || ''
        if (searchInput === currentUrlSearch) return

        const timeoutId = setTimeout(() => {
            updateURL({ search: searchInput, page: '1' })
        }, 500)

        return () => clearTimeout(timeoutId)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchInput, router.isReady])


    const handleSort = (e) => {
        updateURL({ sort: e.target.value, page: '1' })
    }

    const handleLimitChange = (e) => {
        updateURL({ limit: e.target.value, page: '1' })
    }

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            updateURL({ page: newPage.toString() })
            window.scrollTo({ top: 0, behavior: 'smooth' })
        }
    }

    // View Toggle Handler
    const handleViewModeChange = (mode) => {
        if (mode === 'individual') {
            updateURL({}, '/')
        }
        // If already grouped, do nothing (stay here)
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

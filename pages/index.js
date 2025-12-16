import Head from 'next/head'
import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'
import BeerTable from '../components/BeerTable'
import Pagination from '../components/Pagination'
import BeerFilters from '../components/BeerFilters'

// Debug Logger Removed

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }
    static getDerivedStateFromError(error) { return { hasError: true, error }; }
    componentDidCatch(error, errorInfo) { console.error("Uncaught error:", error, errorInfo); }
    render() {
        if (this.state.hasError) {
            return (
                <div style={{ padding: 20, color: 'red' }}>
                    <h2>⚠️ Something went wrong.</h2>
                    <p>{this.state.error?.toString()}</p>
                    <button onClick={() => window.location.reload()}>Reload Page</button>
                </div>
            );
        }
        return this.props.children;
    }
}

export default function Home() {
    return (
        <ErrorBoundary>
            <HomeContent />
        </ErrorBoundary>
    )
}

function HomeContent() {
    const router = useRouter()
    // console.log("[Render] HomeContent rendering. isReady:", router.isReady);

    // State for data
    const [beers, setBeers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [totalPages, setTotalPages] = useState(0)
    const [totalItems, setTotalItems] = useState(0)

    // UI State
    const [searchInput, setSearchInput] = useState('')
    const [isFilterOpen, setIsFilterOpen] = useState(false)
    const [availableStyles, setAvailableStyles] = useState([])
    const [availableBreweries, setAvailableBreweries] = useState([])

    // View Mode (Fixed as 'individual' for index.js)
    const viewMode = 'individual';
    const handleViewModeChange = (mode) => {
        if (mode === 'grouped') {
            router.push('/grouped');
        }
    }

    // Filter UI State
    const [tempFilters, setTempFilters] = useState({
        min_abv: '',
        max_abv: '',
        min_ibu: '',
        max_ibu: '',
        min_rating: '',
        stock_filter: '',
        untappd_status: '',
        shop: '',
        brewery_filter: '',
        style_filter: ''
    })

    // Derived state from URL (defaults)
    const page = parseInt(router.query.page || '1', 10)
    const limit = router.query.limit || '20'
    const sort = router.query.sort || 'newest'

    // Initialize search input from URL
    useEffect(() => {
        if (router.isReady) {
            setSearchInput(router.query.search || '')
            setTempFilters({
                min_abv: router.query.min_abv || '',
                max_abv: router.query.max_abv || '',
                min_ibu: router.query.min_ibu || '',
                max_ibu: router.query.max_ibu || '',
                min_rating: router.query.min_rating || '',
                stock_filter: router.query.stock_filter || '',
                untappd_status: router.query.untappd_status || '',
                shop: router.query.shop || '',
                brewery_filter: router.query.brewery_filter || '',
                style_filter: router.query.style_filter || ''
            })

            fetch('/api/styles').then(res => res.json()).then(d => d.styles && setAvailableStyles(d.styles)).catch(console.error)
            fetch('/api/breweries').then(res => res.json()).then(d => d.breweries && setAvailableBreweries(d.breweries)).catch(console.error)
        }
    }, [router.isReady])

    // Data Fetching
    const fetchBeers = useCallback(async () => {
        // console.log("[Fetch] fetchBeers called. isReady:", router.isReady);

        if (!router.isReady) {
            // console.log("[Fetch] Router not ready, aborting.");
            return;
        }

        // console.log("Fetching beers with query:", JSON.stringify(router.query));
        setLoading(true)
        setError(null)

        // Timeout logic
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        try {
            const currentParams = router.query
            const params = new URLSearchParams({
                page: currentParams.page || '1',
                limit: currentParams.limit || '20',
                search: currentParams.search || '',
                sort: currentParams.sort || 'newest',
            })
            if (currentParams.shop) params.append('shop', currentParams.shop)

            const filterKeys = ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'untappd_status']
            filterKeys.forEach(key => { if (currentParams[key]) params.append(key, currentParams[key]) })

            const res = await fetch(`/api/beers?${params}`, { signal: controller.signal })
            clearTimeout(timeoutId);

            if (!res.ok) throw new Error('Failed to load beers')
            const data = await res.json()

            // console.log('Fetched:', data.beers?.length);
            setBeers(data.beers || [])
            setTotalPages(data.pagination.totalPages)
            setTotalItems(data.pagination.total)
        } catch (err) {
            console.error('Fetch error:', err);
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }, [router.isReady, router.query])

    // Fetch on URL change
    useEffect(() => {
        fetchBeers()
    }, [fetchBeers])

    // Helper to update URL
    const updateURL = (newParams, pathname = '/') => {
        const query = { ...router.query, ...newParams }
        // Cleanups
        if (query.page == '1') delete query.page
        if (query.limit == '20') delete query.limit
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        if (!query.shop) delete query.shop
        const filterKeys = ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'untappd_status']
        filterKeys.forEach(key => { if (!query[key]) delete query[key] })
        router.push({ pathname, query }, undefined, { scroll: false })
    }

    const activeFilterCount = (() => {
        if (!router.isReady) return 0
        const keys = ['min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'shop', 'style_filter', 'brewery_filter', 'untappd_status']
        return keys.filter(k => !!router.query[k]).length
    })()

    const handleFilterChange = (key, value) => {
        updateURL({ [key]: value, page: '1' })
        setTempFilters(prev => ({ ...prev, [key]: value }))
    }

    const handleMultiSelectChange = (key, value) => {
        handleFilterChange(key, value.join(','))
    }

    const resetFilters = () => {
        setSearchInput('')
        setTempFilters({
            min_abv: '', max_abv: '', min_ibu: '', max_ibu: '', min_rating: '', stock_filter: '', untappd_status: '', shop: '', brewery_filter: '', style_filter: ''
        })
        router.push({ pathname: '/', query: {} }, undefined, { scroll: false })
    }

    const handleSearchChange = (e) => {
        const val = e.target.value
        setSearchInput(val)
        // Debounce logic handled by simple timeout in user typing usually, but here we can just update URL on blur or verify debounce
        // Simplified for this replacement:
        if (window.searchTimeout) clearTimeout(window.searchTimeout)
        window.searchTimeout = setTimeout(() => updateURL({ search: val, page: '1' }), 500)
    }

    const handleSort = (e) => updateURL({ sort: e.target.value, page: '1' })
    const handleLimitChange = (e) => updateURL({ limit: e.target.value, page: '1' })
    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            updateURL({ page: newPage.toString() })
            window.scrollTo({ top: 0, behavior: 'smooth' })
        }
    }

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
                        <Link href="/" style={{ textDecoration: 'none', color: 'inherit' }}>
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
                        {searchInput && (
                            <button
                                className="clear-search-btn"
                                onClick={() => { setSearchInput(''); updateURL({ search: '', page: '1' }) }}
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
                    shop={tempFilters.shop}
                    brewery_filter={tempFilters.brewery_filter}
                    style_filter={tempFilters.style_filter}
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
                    viewMode={viewMode}
                    onViewModeChange={handleViewModeChange}
                    onRefresh={fetchBeers}
                />

                <BeerTable
                    beers={beers}
                    loading={loading}
                    error={error}
                />

                {!loading && !error && (
                    <Pagination
                        currentPage={page}
                        totalPages={totalPages}
                        onPageChange={handlePageChange}
                    />
                )}
            </main>

            <footer className="footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Watch Japan. Data sourced from Beervolta &amp; Chouseiya.</p>
                </div>
            </footer>
        </>
    )
}


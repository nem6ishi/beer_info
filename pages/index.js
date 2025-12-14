import Head from 'next/head'
import { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/router'

export default function Home() {
    const router = useRouter()

    // State for data
    const [beers, setBeers] = useState([])
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
        stock_filter: ''
    })

    // Derived state from URL (defaults)
    // Only trust these when router.isReady is true
    // Derived state from URL (defaults)
    const page = parseInt(router.query.page || '1', 10)
    const limit = router.query.limit || '20' // Default limit 20
    const sort = router.query.sort || 'newest'
    const shop = router.query.shop || ''
    const style_filter = router.query.style_filter || ''
    const brewery_filter = router.query.brewery_filter || ''

    // Initialize search input from URL once router is ready. 
    // We use a ref or flag to ensure we only do this once on mount/ready 
    // to avoid overwriting user input if they start typing immediately (edge case)
    // but useEffect [router.isReady] is usually fine.
    // Initial Load
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
                stock_filter: router.query.stock_filter || ''
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
    const fetchBeers = useCallback(async () => {
        if (!router.isReady) return

        setLoading(true)
        setError(null)
        try {
            // Use router.query directly to ensure we fetch what matches the URL
            const currentParams = router.query
            const params = new URLSearchParams({
                page: currentParams.page || '1',
                limit: currentParams.limit || '20', // Dynamic limit
                search: currentParams.search || '',
                sort: currentParams.sort || 'newest',
            })
            if (currentParams.shop) {
                params.append('shop', currentParams.shop)
            }
            // Append advanced filters
            const filterKeys = ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter']
            filterKeys.forEach(key => {
                if (currentParams[key]) params.append(key, currentParams[key])
            })

            const res = await fetch(`/api/beers?${params}`)
            if (!res.ok) throw new Error('Failed to load beers')
            const data = await res.json()

            console.log('Fetched beers:', data.beers?.length, data.pagination);
            setBeers(data.beers || [])
            setTotalPages(data.pagination.totalPages)
            setTotalItems(data.pagination.total)
        } catch (err) {
            console.error('Fetch error:', err);
            setError(err.message)
            console.error(err)
        } finally {
            setLoading(false)
        }
    }, [router.isReady, router.query])

    // Fetch on URL change
    useEffect(() => {
        fetchBeers()
    }, [fetchBeers])

    // Helper to update URL
    const updateURL = (newParams) => {
        const query = { ...router.query, ...newParams }

        // Cleanup defaults to keep URL clean
        if (query.page == '1') delete query.page
        if (query.limit == '20') delete query.limit // Default limit cleanup
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        if (!query.shop) delete query.shop
        // Clean up empty filters
        const filterKeys = ['style_filter', 'brewery_filter', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter']
        filterKeys.forEach(key => {
            if (!query[key]) delete query[key]
        })

        router.push({ pathname: '/', query }, undefined, { scroll: false })
    }

    // Filter Logic
    const activeFilterCount = (() => {
        if (!router.isReady) return 0
        const keys = ['limit', 'min_abv', 'max_abv', 'min_ibu', 'max_ibu', 'min_rating', 'stock_filter', 'shop', 'style_filter', 'brewery_filter'] // Limit acts like a filter param
        return keys.filter(k => !!router.query[k] && k !== 'limit' && k !== 'sort' && k !== 'page').length // Exclude structural params from badge count
    })()

    // Generic handler for Advanced Filters (Auto-Apply with debounce for inputs?)
    // User wants "instant apply". For text/num inputs, we need debounce. For selects, instant.
    // Let's debounce the hook updates for range inputs.

    // We update tempFilters state immediately for UI 
    const handleFilterChange = (key, value) => {
        setTempFilters(prev => ({ ...prev, [key]: value }))

        // If it's a select (Stock), update URL immediately
        if (key === 'stock_filter') {
            updateURL({ [key]: value, page: '1' })
        }
    }

    // Debounced effect for Advanced Filters (ABV, IBU, Rating)
    useEffect(() => {
        if (!router.isReady) return

        // Prevent loop: check if values changed from URL
        // Actually, just debounce the update call.
        const timeoutId = setTimeout(() => {
            // Only update if these specific keys changed compared to current URL?
            // Or just update. updateURL handles merging.
            // But we don't want to overwrite other params.

            // Let's only update if tempFilters differ from URL params?
            // To keep it simple: just fire updateURL with current tempFilters.
            // But exclude 'stock_filter' if we handled it instantly, or just include all.
            // Including all is safer.

            // Check if any of these diff from router.query to avoid infinite loop or unnecessary pushes?
            // router.push is smart enough usually, but let's be safe.
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
    }, [tempFilters, router.isReady]) // Trigger when tempFilters change

    // Handler for Multi-Selects (Immediate URL update)
    const handleMultiSelectChange = (paramKey, newValues) => {
        // newValues is array of strings
        // join by comma
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
            stock_filter: ''
        }
        setTempFilters(resetState)
        setSearchInput('') // Clear search input

        // Update URL to clear advanced filters AND sort/search
        updateURL({
            min_abv: '',
            max_abv: '',
            min_ibu: '',
            max_ibu: '',
            min_rating: '',
            stock_filter: '',
            shop: '', // Clear shop filter
            style_filter: '', // Clear style filter
            brewery_filter: '', // Clear brewery filter
            sort: 'newest', // Reset sort
            search: '', // Clear search param
            page: '1'
        })
    }

    // Handlers
    const handleSearchChange = (e) => {
        setSearchInput(e.target.value)
    }

    // Debounce search update to URL
    useEffect(() => {
        if (!router.isReady) return

        // Check if current input matches current URL param to avoid redundant pushes
        const currentUrlSearch = router.query.search || ''
        if (searchInput === currentUrlSearch) return

        const timeoutId = setTimeout(() => {
            updateURL({ search: searchInput, page: '1' })
        }, 500) // 500ms debounce

        return () => clearTimeout(timeoutId)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchInput, router.isReady])
    // Removed router.query.search from deps to avoid loops, though strict equality check handles it.
    // We mainly want to react to searchInput changes.


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

    const formatPrice = (price) => {
        if (!price) return '¥-';
        if (price.includes('¥')) return price;
        const num = parseInt(price.replace(/[^0-9]/g, ''), 10);
        if (isNaN(num)) return price;
        return new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY' }).format(num);
    }

    const formatDate = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleDateString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    const formatSimpleDate = (isoString) => {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleDateString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
        });
    }

    return (
        <>
            <Head>
                <meta charSet="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Craft Beer Alert Japan</title>
                <meta name="description" content="Discover premium craft beers collected from the best Japanese shops." />
            </Head>

            <div className="background-globes">
                <div className="globe globe-1"></div>
                <div className="globe globe-2"></div>
            </div>

            <header className="glass-header">
                <div className="container header-content">
                    <h1>
                        <Link href="/" style={{ textDecoration: 'none', color: 'inherit' }}>
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
                <div className="controls-bar">
                    {/* Shop Filter (Multi-Select) */}
                    <div className="filter-group-main">
                        <label className="sort-label">Store:</label>
                        <MultiSelectDropdown
                            options={[
                                { value: 'BEER VOLTA', label: 'BEER VOLTA' },
                                { value: 'ちょうせいや', label: 'ちょうせいや' },
                                { value: '一期一会～る', label: '一期一会～る' }
                            ]}
                            selectedValues={shop ? shop.split(',') : []}
                            onChange={(vals) => handleMultiSelectChange('shop', vals)}
                            placeholder="Select Stores"
                        />
                    </div>

                    {/* Breweries Dropdown (Multi-select) */}
                    <div className="filter-group-main">
                        <button className="dropdown-toggle" style={{ display: 'none' }}>Breweries</button> {/* Hidden dummy to keep layout if needed, or just remove */}
                        <label className="sort-label">Breweries:</label>
                        <MultiSelectDropdown
                            options={availableBreweries.map(b => ({ label: b, value: b }))}
                            selectedValues={brewery_filter ? brewery_filter.split(',') : []}
                            onChange={(vals) => updateURL({ brewery_filter: vals.join(','), page: '1' })}
                            placeholder="Select Breweries"
                            searchable={true}
                        />
                    </div>

                    {/* Style Dropdown (Multi-select) */}
                    <div className="filter-group-main">
                        <label className="sort-label">Style:</label>
                        <MultiSelectDropdown
                            options={availableStyles.map(s => ({ value: s, label: s }))}
                            selectedValues={style_filter ? style_filter.split(',') : []}
                            onChange={(vals) => handleMultiSelectChange('style_filter', vals)}
                            placeholder="Select Styles"
                            searchable={true}
                        />
                    </div>

                    {/* Sort (Main Bar) */}
                    <div className="filter-group-main">
                        <label htmlFor="sortSelect" className="sort-label">Sort:</label>
                        <div className="select-wrapper">
                            <select
                                id="sortSelect"
                                className="sort-select"
                                value={sort}
                                onChange={handleSort}
                                aria-label="Sort beers"
                            >
                                <option value="newest">Newest</option>
                                <option value="price_asc">Price: Low to High</option>
                                <option value="price_desc">Price: High to Low</option>
                                <option value="abv_desc">ABV: High to Low</option>
                                <option value="rating_desc">Rating: High to Low</option>
                                <option value="name_asc">Name: A to Z</option>
                            </select>
                        </div>
                    </div>

                    {/* Limit Filter */}
                    <div className="filter-group-main">
                        <label htmlFor="limitSelect" className="sort-label">Limit:</label>
                        <div className="select-wrapper">
                            <select
                                id="limitSelect"
                                className="sort-select"
                                value={limit}
                                onChange={handleLimitChange}
                                aria-label="Items per page"
                                style={{ minWidth: '80px' }}
                            >
                                <option value="20">20</option>
                                <option value="50">50</option>
                                <option value="100">100</option>
                            </select>
                        </div>
                    </div>

                    <div className="controls-divider"></div>

                    {/* Advanced Toggle */}
                    <button
                        className={`open-filter-btn ${isFilterOpen ? 'active' : ''}`}
                        onClick={() => setIsFilterOpen(!isFilterOpen)}
                        aria-expanded={isFilterOpen}
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                        </svg>
                        Detailed Filters
                        {activeFilterCount > 0 && <span className="filter-badge-count">{activeFilterCount}</span>}
                        <span className="toggle-icon">{isFilterOpen ? '▲' : '▼'}</span>
                    </button>

                    {/* Reset Button (Always visible) */}
                    <div className="controls-divider"></div>
                    <button
                        className="reset-btn-small"
                        onClick={resetFilters}
                        title="Reset all filters"
                    >
                        Reset
                    </button>
                </div>

                {/* Collapsible Filter Area */}
                <div className={`filter-collapsible ${isFilterOpen ? 'open' : ''}`}>
                    <div className="filter-content">
                        <div className="filter-grid">

                            {/* ABV Filter */}
                            <div className="filter-item">
                                <label>ABV (%)</label>
                                <div className="input-range-group">
                                    <input
                                        type="number"
                                        className="filter-input"
                                        placeholder="Min"
                                        value={tempFilters.min_abv}
                                        onChange={(e) => handleFilterChange('min_abv', e.target.value)}
                                    />
                                    <span>-</span>
                                    <input
                                        type="number"
                                        className="filter-input"
                                        placeholder="Max"
                                        value={tempFilters.max_abv}
                                        onChange={(e) => handleFilterChange('max_abv', e.target.value)}
                                    />
                                </div>
                            </div>

                            {/* IBU Filter */}
                            <div className="filter-item">
                                <label>IBU</label>
                                <div className="input-range-group">
                                    <input
                                        type="number"
                                        className="filter-input"
                                        placeholder="Min"
                                        value={tempFilters.min_ibu}
                                        onChange={(e) => handleFilterChange('min_ibu', e.target.value)}
                                    />
                                    <span>-</span>
                                    <input
                                        type="number"
                                        className="filter-input"
                                        placeholder="Max"
                                        value={tempFilters.max_ibu}
                                        onChange={(e) => handleFilterChange('max_ibu', e.target.value)}
                                    />
                                </div>
                            </div>

                            {/* Rating Filter */}
                            <div className="filter-item">
                                <label>Rating (Min)</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    className="filter-input"
                                    placeholder="0-5"
                                    value={tempFilters.min_rating}
                                    onChange={(e) => handleFilterChange('min_rating', e.target.value)}
                                />
                            </div>

                            {/* Stock Filter */}
                            <div className="filter-item">
                                <label>Stock</label>
                                <div className="select-wrapper full-width">
                                    <select
                                        className="filter-select"
                                        value={tempFilters.stock_filter}
                                        onChange={(e) => handleFilterChange('stock_filter', e.target.value)}
                                    >
                                        <option value="">All</option>
                                        <option value="in_stock">In Stock Only</option>
                                    </select>
                                </div>
                            </div>
                        </div>


                    </div>
                </div>

                {loading && <div className="status-message">Loading collection...</div>}
                {error && <div className="status-message error">Error: {error}</div>}

                {!loading && !error && (
                    <>
                        <div className="table-container">
                            <table className="beer-table">
                                <thead>
                                    <tr>
                                        <th className="col-img">Image</th>
                                        <th className="col-name">Info</th>
                                        <th className="col-beer-style">Style / Specs</th>
                                        <th className="col-rating">Rating</th>
                                        <th className="col-price">Price</th>
                                        <th className="col-shop">Shop</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {beers.map(beer => (
                                        <tr key={beer.id || beer.url}>
                                            <td className="col-img">
                                                <div className="beer-image-wrapper">
                                                    <img
                                                        src={beer.image}
                                                        alt={beer.name}
                                                        loading="lazy"
                                                        onError={(e) => { e.target.src = 'https://placehold.co/100x100?text=No+Image'; }}
                                                    />
                                                </div>
                                            </td>
                                            <td className="col-name">
                                                <div className="beer-name-group">
                                                    {(beer.untappd_brewery_name || beer.untappd_beer_name || beer.brewery_name_en || beer.brewery_name_jp || beer.beer_name_en || beer.beer_name_jp) ? (
                                                        <>
                                                            <div className="brewery-name">
                                                                {beer.untappd_brewery_name || beer.brewery_name_en || beer.brewery_name_jp || ''}
                                                            </div>
                                                            <div className="beer-name">
                                                                {beer.untappd_beer_name || beer.beer_name_jp || beer.beer_name_en || beer.name}
                                                            </div>
                                                        </>
                                                    ) : beer.name === 'Unknown' ? (
                                                        <div className="beer-name" style={{ color: '#999', fontStyle: 'italic' }}>
                                                            商品情報取得中... <a href={beer.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8em' }}>詳細を見る</a>
                                                        </div>
                                                    ) : (
                                                        <div className="beer-name">{beer.name}</div>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="col-beer-style">
                                                <div className="style-specs-group">
                                                    {beer.untappd_style ? (
                                                        <span className="beer-style-text">{beer.untappd_style}</span>
                                                    ) : (
                                                        <span className="na-text">Top Style N/A</span>
                                                    )}
                                                    <div className="stats-row">
                                                        <div className="stat-item">
                                                            {beer.untappd_abv ? `${beer.untappd_abv.toString().includes('%') ? Number(beer.untappd_abv.replace('%', '')).toFixed(1) : Number(beer.untappd_abv).toFixed(1)}% ABV` : <span className="na-text">N/A ABV</span>}
                                                        </div>
                                                        <span className="separator">•</span>
                                                        <div className="stat-item">
                                                            {beer.untappd_ibu ? `${Number(beer.untappd_ibu.toString().replace(/[^0-9.]/g, '')).toFixed(0)} IBU` : <span className="na-text">N/A IBU</span>}
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="col-rating">
                                                <div className="rating-box">
                                                    {beer.untappd_url ? (
                                                        <a href={beer.untappd_url} target="_blank" rel="noopener noreferrer" className="untappd-badge-link">
                                                            <span className="untappd-header">UNTAPPD ↗</span>
                                                            {beer.untappd_rating ? (
                                                                <span className="untappd-badge">{Number(beer.untappd_rating).toFixed(2)}</span>
                                                            ) : (
                                                                <span className="untappd-badge na">N/A</span>
                                                            )}
                                                        </a>
                                                    ) : (
                                                        beer.untappd_rating ? (
                                                            <div className="untappd-badge-container">
                                                                <span className="untappd-header">UNTAPPD</span>
                                                                <span className="untappd-badge">{Number(beer.untappd_rating).toFixed(2)}</span>
                                                            </div>
                                                        ) : (
                                                            <span className="na-text">N/A</span>
                                                        )
                                                    )}
                                                    {beer.untappd_rating_count > 0 && (
                                                        <span className="rating-count">({beer.untappd_rating_count})</span>
                                                    )}
                                                    {beer.untappd_fetched_at && (
                                                        <span className="fetched-date">Checked: {formatSimpleDate(beer.untappd_fetched_at)}</span>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="col-price">
                                                <span className="price-tag">{formatPrice(beer.price)}</span>
                                            </td>
                                            <td className="col-shop">
                                                <div className="shop-info-group">
                                                    <a href={beer.url} target="_blank" rel="noopener noreferrer" className="shop-btn">
                                                        {beer.shop} ↗
                                                    </a>
                                                    {beer.stock_status && (
                                                        <span className={`stock-badge ${beer.stock_status.toLowerCase().includes('out') ? 'out-of-stock' : 'in-stock'}`}>
                                                            {beer.stock_status}
                                                        </span>
                                                    )}
                                                    <div className="date-display">
                                                        Checked: {formatSimpleDate(beer.first_seen)}
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                    {beers.length === 0 && (
                                        <tr>
                                            <td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>
                                                No beers found matching your criteria.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>

                        {totalPages > 1 && (
                            <div className="pagination-wrapper">
                                <div className="total-count">
                                    Total: {totalItems} beers
                                </div>
                                <div className="pagination-controls">
                                    {/* First Page */}
                                    <button
                                        className="page-btn icon-btn"
                                        disabled={page <= 1}
                                        onClick={() => handlePageChange(1)}
                                        aria-label="First Page"
                                    >
                                        «
                                    </button>

                                    {/* Previous */}
                                    <button
                                        className="page-btn"
                                        disabled={page <= 1}
                                        onClick={() => handlePageChange(page - 1)}
                                    >
                                        ‹ Prev
                                    </button>

                                    {/* Page Numbers */}
                                    <div className="page-numbers">
                                        {(() => {
                                            const pages = [];
                                            const maxVisible = 7; // Total number of slots (1, ..., 4, 5, 6, ..., 100)

                                            if (totalPages <= maxVisible) {
                                                for (let i = 1; i <= totalPages; i++) pages.push(i);
                                            } else {
                                                // Always show 1
                                                pages.push(1);

                                                // Determine start and end of sliding window
                                                let start = Math.max(2, page - 1);
                                                let end = Math.min(totalPages - 1, page + 1);

                                                // Adjust if at edges
                                                if (page <= 3) {
                                                    end = 4; // 1, 2, 3, 4 ...
                                                }
                                                if (page >= totalPages - 2) {
                                                    start = totalPages - 3; // ... 97, 98, 99, 100
                                                }

                                                // Add left ellipsis
                                                if (start > 2) {
                                                    pages.push('...');
                                                }

                                                // Add window
                                                for (let i = start; i <= end; i++) {
                                                    pages.push(i);
                                                }

                                                // Add right ellipsis
                                                if (end < totalPages - 1) {
                                                    pages.push('...');
                                                }

                                                // Always show last
                                                pages.push(totalPages);
                                            }

                                            return pages.map((p, idx) => (
                                                p === '...' ? (
                                                    <span key={`ellipsis-${idx}`} className="page-ellipsis">...</span>
                                                ) : (
                                                    <button
                                                        key={p}
                                                        className={`page-number ${p === page ? 'active' : ''}`}
                                                        onClick={() => handlePageChange(p)}
                                                    >
                                                        {p}
                                                    </button>
                                                )
                                            ));
                                        })()}
                                    </div>

                                    {/* Next */}
                                    <button
                                        className="page-btn"
                                        disabled={page >= totalPages}
                                        onClick={() => handlePageChange(page + 1)}
                                    >
                                        Next ›
                                    </button>

                                    {/* Last Page */}
                                    <button
                                        className="page-btn icon-btn"
                                        disabled={page >= totalPages}
                                        onClick={() => handlePageChange(totalPages)}
                                        aria-label="Last Page"
                                    >
                                        »
                                    </button>

                                </div>
                            </div>
                        )}
                    </>
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

// --- Components ---

function MultiSelectDropdown({ options, selectedValues, onChange, placeholder, searchable = false }) {
    const [isOpen, setIsOpen] = useState(false)
    const [searchTerm, setSearchTerm] = useState('')
    const containerRef = useRef(null)

    // Close on click outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false)
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [containerRef]);

    const handleToggle = (value) => {
        const newValues = selectedValues.includes(value)
            ? selectedValues.filter(v => v !== value)
            : [...selectedValues, value]
        onChange(newValues)
    }

    const filteredOptions = searchable
        ? options.filter(opt => opt.label.toLowerCase().includes(searchTerm.toLowerCase()))
        : options

    const getDisplayLabel = () => {
        if (selectedValues.length === 0) return placeholder
        if (selectedValues.length === 1) return selectedValues[0] // or map to label
        return `${selectedValues.length} selected`
    }

    return (
        <div className="multi-select-container" ref={containerRef}>
            <button
                className={`multi-select-trigger ${isOpen ? 'active' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className="truncate">{getDisplayLabel()}</span>
                <span className="arrow">▼</span>
            </button>

            {isOpen && (
                <div className="multi-select-dropdown">
                    {searchable && (
                        <div className="multi-select-search">
                            <input
                                type="text"
                                placeholder="Search..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                autoFocus
                            />
                        </div>
                    )}
                    <div className="multi-select-options">
                        {filteredOptions.length > 0 ? (
                            filteredOptions.map((option) => (
                                <label key={option.value} className="multi-select-option">
                                    <input
                                        type="checkbox"
                                        checked={selectedValues.includes(option.value)}
                                        onChange={() => handleToggle(option.value)}
                                    />
                                    <span>{option.label}</span>
                                </label>
                            ))
                        ) : (
                            <div className="no-options">No options</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

import Head from 'next/head'
import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/router'

export default function Home() {
    const router = useRouter()

    // State for data
    const [beers, setBeers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [totalPages, setTotalPages] = useState(0)
    const [totalItems, setTotalItems] = useState(0)

    // Local state for search input to allow immediate feedback while typing
    const [searchInput, setSearchInput] = useState('')

    // Derived state from URL (defaults)
    // Only trust these when router.isReady is true
    const page = parseInt(router.query.page || '1', 10)
    const sort = router.query.sort || 'newest'
    const shop = router.query.shop || ''

    // Initialize search input from URL once router is ready. 
    // We use a ref or flag to ensure we only do this once on mount/ready 
    // to avoid overwriting user input if they start typing immediately (edge case)
    // but useEffect [router.isReady] is usually fine.
    useEffect(() => {
        if (router.isReady) {
            setSearchInput(router.query.search || '')
        }
    }, [router.isReady]) // Only run once when ready

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
                limit: '30',
                search: currentParams.search || '',
                sort: currentParams.sort || 'newest',
            })
            if (currentParams.shop) {
                params.append('shop', currentParams.shop)
            }

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
        if (query.sort === 'newest') delete query.sort
        if (!query.search) delete query.search
        if (!query.shop) delete query.shop

        router.push({ pathname: '/', query }, undefined, { scroll: false })
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

    const handleShopFilter = (e) => {
        updateURL({ shop: e.target.value, page: '1' })
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
                    <h1>Craft Beer Alert Japan (v2)</h1>
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
                    </div>
                </div>
            </header>

            <main className="container">
                <div className="controls-bar">
                    <div className="sort-container">
                        <label htmlFor="shopFilter" className="sort-label">Store:</label>
                        <div className="select-wrapper">
                            <select
                                id="shopFilter"
                                className="sort-select"
                                value={shop}
                                onChange={handleShopFilter}
                            >
                                <option value="">All Stores</option>
                                <option value="BEER VOLTA">BEER VOLTA</option>
                                <option value="ちょうせいや">ちょうせいや</option>
                                <option value="一期一会～る">一期一会～る</option>
                            </select>
                        </div>
                    </div>
                    <div className="sort-container">
                        <label htmlFor="sortSelect" className="sort-label">Sort by:</label>
                        <div className="select-wrapper">
                            <select
                                id="sortSelect"
                                className="sort-select"
                                value={sort}
                                onChange={handleSort}
                            >
                                <option value="newest">Newest Arrival</option>
                                <option value="price_asc">Price: Low to High</option>
                                <option value="price_desc">Price: High to Low</option>
                                <option value="abv_desc">ABV: High to Low</option>
                                <option value="rating_desc">Untappd Rating: High to Low</option>
                                <option value="name_asc">Name: A to Z</option>
                            </select>
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
                                        <th className="col-beer-style">Style</th>
                                        <th className="col-style">ABV / IBU</th>
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
                                                                {beer.untappd_url ? (
                                                                    <a href={beer.untappd_url} target="_blank" rel="noopener noreferrer" className="untappd-link">
                                                                        {beer.untappd_beer_name || beer.beer_name_jp || beer.beer_name_en || beer.name}
                                                                        <span className="external-icon"> ↗</span>
                                                                    </a>
                                                                ) : (
                                                                    beer.untappd_beer_name || beer.beer_name_jp || beer.beer_name_en || beer.name
                                                                )}
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
                                                <span className="beer-style-text">{beer.untappd_style || 'N/A'}</span>
                                            </td>
                                            <td className="col-style">
                                                <div className="stats-stack">
                                                    <div className="stat-item">
                                                        {beer.untappd_abv ? `${beer.untappd_abv} ABV` : 'N/A ABV'}
                                                    </div>
                                                    <div className="stat-item">
                                                        {beer.untappd_ibu ? `${beer.untappd_ibu} IBU` : 'N/A IBU'}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="col-rating">
                                                <div className="rating-box">
                                                    {beer.untappd_rating ? (
                                                        <>
                                                            {beer.untappd_url ? (
                                                                <a href={beer.untappd_url} target="_blank" rel="noopener noreferrer" className="rating-link-group">
                                                                    <div className="rating-score-row">
                                                                        <span className="rating-score">{Number(beer.untappd_rating).toFixed(2)}</span>
                                                                        <span className="untappd-label">Untappd ↗</span>
                                                                    </div>
                                                                </a>
                                                            ) : (
                                                                <span className="rating-score">{Number(beer.untappd_rating).toFixed(2)}</span>
                                                            )}
                                                            <span className="rating-count">({beer.untappd_rating_count || 0})</span>
                                                            {beer.untappd_fetched_at && (
                                                                <span className="fetched-date">Updated: {formatSimpleDate(beer.untappd_fetched_at)}</span>
                                                            )}
                                                        </>
                                                    ) : (
                                                        <span className="na-text">N/A</span>
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
                                                        Checked: {formatDate(beer.first_seen)}
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
                        )}
                    </>
                )}
            </main>

            <footer className="glass-footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Watch Japan. Data sourced from Beervolta &amp; Chouseiya.</p>
                </div>
            </footer>
        </>
    )
}

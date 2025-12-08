import Head from 'next/head'
import { useState, useEffect, useCallback } from 'react'

export default function Home() {
    // State
    const [beers, setBeers] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [search, setSearch] = useState('')
    const [sort, setSort] = useState('newest')
    const [shop, setShop] = useState('')
    const [page, setPage] = useState(1)
    const [totalPages, setTotalPages] = useState(0)
    const [totalItems, setTotalItems] = useState(0)

    // Data Fetching
    const fetchBeers = useCallback(async () => {
        setLoading(true)
        setError(null)
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '30',
                search,
                sort
            })
            if (shop) {
                params.append('shop', shop)
            }
            const res = await fetch(`/api/beers?${params}`)
            if (!res.ok) throw new Error('Failed to load beers')
            const data = await res.json()

            setBeers(data.beers || [])
            setTotalPages(data.pagination.totalPages)
            setTotalItems(data.pagination.total)
        } catch (err) {
            setError(err.message)
            console.error(err)
        } finally {
            setLoading(false)
        }
    }, [page, search, sort, shop])

    // Effects
    useEffect(() => {
        fetchBeers()
    }, [fetchBeers])

    // Handlers
    const handleSearch = (e) => {
        setSearch(e.target.value)
        setPage(1)
    }

    const handleSort = (e) => {
        setSort(e.target.value)
        setPage(1)
    }

    const handleShopFilter = (e) => {
        setShop(e.target.value)
        setPage(1)
    }

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= totalPages) {
            setPage(newPage)
            window.scrollTo({ top: 0, behavior: 'smooth' })
        }
    }

    const formatPrice = (price) => {
        if (!price) return '¥-';
        // Basic check if it already has yen symbol
        if (price.includes('¥')) return price;
        // Try to format as number if possible
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
            minute: '2-digit'
        });
    }

    return (
        <>
            <Head>
                <meta charSet="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Craft Beer Watch Japan</title>
                <meta name="description" content="Discover premium craft beers collected from the best Japanese shops." />
            </Head>

            <header className="glass-header">
                <div className="container header-content">
                    <h1>Craft Beer Alert Japan</h1>
                    <div className="search-bar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                            strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                        <input
                            type="text"
                            placeholder="Search beers..."
                            value={search}
                            onChange={handleSearch}
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
                                        <th className="col-name">Beer Info</th>
                                        <th className="col-style">Style / Stats</th>
                                        <th className="col-price">Price</th>
                                        <th className="col-untappd">Untappd</th>
                                        <th className="col-shop">Shop</th>
                                        <th className="col-registered">Available Since</th>
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
                                                    <div className="brewery-name">{beer.brewery_name_en || beer.brewery_name_jp || 'Unknown Brewery'}</div>
                                                    <div className="beer-name">{beer.beer_name_en || beer.beer_name_jp || beer.name}</div>
                                                    {beer.stock_status && (
                                                        <span className={`stock-badge ${beer.stock_status.toLowerCase().includes('out') ? 'out-of-stock' : 'in-stock'}`}>
                                                            {beer.stock_status}
                                                        </span>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="col-style">
                                                <div className="style-stats">
                                                    {beer.untappd_style && <div className="beer-style">{beer.untappd_style}</div>}
                                                    <div className="stats-row">
                                                        {beer.untappd_abv && <span className="stat-pill abv">ABV {beer.untappd_abv}%</span>}
                                                        {beer.untappd_ibu && beer.untappd_ibu > 0 && <span className="stat-pill ibu">IBU {beer.untappd_ibu}</span>}
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="col-price">
                                                <span className="price-tag">{formatPrice(beer.price)}</span>
                                            </td>
                                            <td className="col-untappd">
                                                {beer.untappd_rating ? (
                                                    <div className="rating-box">
                                                        <span className="rating-score">★ {Number(beer.untappd_rating).toFixed(2)}</span>
                                                        <span className="rating-count">({beer.untappd_rating_count})</span>
                                                    </div>
                                                ) : <span className="no-rating">-</span>}
                                                {beer.untappd_url && (
                                                    <a href={beer.untappd_url} target="_blank" rel="noopener noreferrer" className="untappd-link">
                                                        View on Untappd
                                                    </a>
                                                )}
                                            </td>
                                            <td className="col-shop">
                                                <a href={beer.url} target="_blank" rel="noopener noreferrer" className="shop-btn">
                                                    {beer.shop} ↗
                                                </a>
                                            </td>
                                            <td className="col-registered">
                                                <div className="date-display">
                                                    {formatDate(beer.available_since || beer.first_seen).split(' ').map((line, i) => (
                                                        <span key={i} className="date-line">{line}</span>
                                                    ))}
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
                                <button
                                    className="page-btn"
                                    disabled={page <= 1}
                                    onClick={() => handlePageChange(page - 1)}
                                >
                                    ← Previous
                                </button>
                                <span className="page-info">
                                    Page {page} of {totalPages} <span className="total-items">({totalItems} beers)</span>
                                </span>
                                <button
                                    className="page-btn"
                                    disabled={page >= totalPages}
                                    onClick={() => handlePageChange(page + 1)}
                                >
                                    Next →
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

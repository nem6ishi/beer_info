import React from 'react'

export default function BeerTable({ beers, loading, error }) {

    const formatPrice = (price) => {
        if (!price) return '¥-';
        if (price.includes('¥')) return price;
        const num = parseInt(price.replace(/[^0-9]/g, ''), 10);
        if (isNaN(num)) return price;
        return new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY' }).format(num);
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

    if (loading) return <div className="status-message">Loading collection...</div>
    if (error) return <div className="status-message error">Error: {error}</div>

    return (
        <div className="table-container">
            <table className="beer-table">
                <thead>
                    <tr>
                        <th className="col-img">Image</th>
                        <th className="col-name">Info</th>
                        <th className="col-beer-style">Style / Specs</th>
                        <th className="col-rating">Rating</th>
                        <th className="col-shop">Availability</th>
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
                                        <span className="fetched-date">{formatSimpleDate(beer.untappd_fetched_at)}</span>
                                    )}
                                </div>
                            </td>
                            <td className="col-shop">
                                <div className="shop-list-flat">
                                    <div className="shop-item-flat">
                                        <a href={beer.url} target="_blank" rel="noopener noreferrer" className="shop-btn-flat">
                                            <div className="shop-info-primary">
                                                <span className="price-text">
                                                    {formatPrice(beer.price)}
                                                </span>
                                                <span className="shop-name-text">{beer.shop}</span>
                                                {beer.stock_status && (
                                                    <span className={`stock-dot ${beer.stock_status.toLowerCase().includes('out') ? 'out' : 'in'}`} title={beer.stock_status}>
                                                    </span>
                                                )}
                                            </div>
                                            <div className="shop-info-secondary">
                                                <span className="check-date">
                                                    {formatSimpleDate(beer.first_seen)}
                                                </span>
                                                <span className="external-link-arrow">↗</span>
                                            </div>
                                        </a>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    ))}
                    {beers.length === 0 && (
                        <tr>
                            <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                                No beers found matching your criteria.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

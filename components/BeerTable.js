import React from 'react'

export default function BeerTable({ beers, loading, error }) {

    const formatPrice = (price) => {
        if (!price) return '¥-';
        // Simple numeric cleanup
        const num = typeof price === 'number' ? price : parseInt(price.replace(/[^0-9]/g, ''), 10);
        if (isNaN(num)) return price;
        return `¥${num.toLocaleString()}`;
    }

    // Simplified date formatter
    const formatSimpleDate = (isoString) => {
        if (!isoString) return '-';
        try {
            // Safari friendly date parsing
            const date = new Date(isoString.replace(' ', 'T'));
            if (isNaN(date.getTime())) return '-';
            return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
        } catch (e) { return '-'; }
    }

    if (error) return <div className="status-message error">Error: {error}</div>

    // Don't block render on loading. Show table with opacity if reloading.
    // If initial load and no data, show a simple loading message in a container to prevent CLS if possible, 
    // but here we prioritize simplicity.
    if (loading && beers.length === 0) {
        return <div className="status-message">Loading...</div>
    }

    return (
        <div className="table-container" style={{ opacity: loading ? 0.6 : 1, transition: 'opacity 0.2s' }}>
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
                                    <div className="brewery-name">
                                        {beer.untappd_brewery_name || beer.brewery_name_en || beer.brewery_name_jp || ''}
                                    </div>
                                    <div className="beer-name">
                                        {beer.untappd_beer_name || beer.beer_name_jp || beer.beer_name_en || beer.name}
                                    </div>
                                </div>
                            </td>
                            <td className="col-beer-style">
                                <div className="style-specs-group">
                                    <span className={beer.untappd_style ? "beer-style-text" : "na-text"}>
                                        {beer.untappd_style || 'Style N/A'}
                                    </span>
                                    <div className="stats-row">
                                        <div className="stat-item">
                                            {beer.untappd_abv ? `${beer.untappd_abv}% ABV` : <span className="na-text">Top ABV N/A</span>}
                                        </div>
                                        <span className="separator">•</span>
                                        <div className="stat-item">
                                            {beer.untappd_ibu ? `${beer.untappd_ibu} IBU` : <span className="na-text">IBU N/A</span>}
                                        </div>
                                    </div>
                                </div>
                            </td>
                            <td className="col-rating">
                                <div className="rating-box">
                                    {beer.untappd_rating ? (
                                        <a href={beer.untappd_url || '#'} target="_blank" rel="noopener noreferrer" className="untappd-badge-link">
                                            <span className="untappd-badge">{Number(beer.untappd_rating).toFixed(2)}</span>
                                            {beer.untappd_rating_count && <span className="rating-count">({beer.untappd_rating_count})</span>}
                                        </a>
                                    ) : (
                                        <span className="na-text">N/A</span>
                                    )}
                                </div>
                            </td>
                            <td className="col-shop">
                                <div className="shop-list-flat">
                                    <a href={beer.url} target="_blank" rel="noopener noreferrer" className="shop-btn-flat">
                                        <div className="shop-info-primary">
                                            <span className="price-text">{formatPrice(beer.price)}</span>
                                            <span className="shop-name-text">{beer.shop}</span>
                                        </div>
                                        <div className="shop-info-secondary">
                                            <span className="check-date">{formatSimpleDate(beer.first_seen)}</span>
                                            <span className="external-link-arrow">↗</span>
                                        </div>
                                    </a>
                                </div>
                            </td>
                        </tr>
                    ))}
                    {beers.length === 0 && !loading && (
                        <tr>
                            <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                                No beers found.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

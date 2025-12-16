import React from 'react'

export default function GroupedBeerTable({ groups, loading, error }) {

    const formatPrice = (price) => {
        if (!price) return '¥-';
        const num = typeof price === 'number' ? price : parseInt(price.replace(/[^0-9]/g, ''), 10);
        if (isNaN(num)) return price;
        return `¥${num.toLocaleString()}`;
    }

    // Simplified date formatter
    const formatSimpleDate = (isoString) => {
        if (!isoString) return '-';
        try {
            const date = new Date(isoString.replace(' ', 'T'));
            if (isNaN(date.getTime())) return '-';
            return `${date.getFullYear()}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
        } catch (e) { return '-'; }
    }

    if (error) return <div className="status-message error">Error: {error}</div>

    if (loading && groups.length === 0) {
        return <div className="status-message">Loading grouped collection...</div>
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
                    {groups.map(group => {
                        const sortedItems = [...(group.items || [])].sort((a, b) => (a.price_value || Infinity) - (b.price_value || Infinity));
                        const cheapestItem = sortedItems[0];
                        const displayImage = (cheapestItem && cheapestItem.image) ? cheapestItem.image : group.beer_image;

                        return (
                            <tr key={group.untappd_url || group.url}>
                                <td className="col-img">
                                    <div className="beer-image-wrapper">
                                        <img
                                            src={displayImage}
                                            alt={group.beer_name}
                                            loading="lazy"
                                            onError={(e) => { e.target.src = 'https://placehold.co/100x100?text=No+Image'; }}
                                        />
                                    </div>
                                </td>
                                <td className="col-name">
                                    <div className="beer-name-group">
                                        <div className="brewery-name">
                                            {group.brewery || 'Unknown Brewery'}
                                        </div>
                                        <div className="beer-name">
                                            {group.beer_name || 'Unknown Beer'}
                                        </div>
                                    </div>
                                </td>
                                <td className="col-beer-style">
                                    <div className="style-specs-group">
                                        <span className={group.style ? "beer-style-text" : "na-text"}>
                                            {group.style || 'Style N/A'}
                                        </span>
                                        <div className="stats-row">
                                            <div className="stat-item">
                                                {group.abv ? `${group.abv}% ABV` : <span className="na-text">N/A ABV</span>}
                                            </div>
                                            <span className="separator">•</span>
                                            <div className="stat-item">
                                                {group.ibu ? `${group.ibu} IBU` : <span className="na-text">N/A IBU</span>}
                                            </div>
                                        </div>
                                    </div>
                                </td>
                                <td className="col-rating">
                                    <div className="rating-box">
                                        {group.untappd_url ? (
                                            <a href={group.untappd_url} target="_blank" rel="noopener noreferrer" className="untappd-badge-link">
                                                <span className="untappd-header">UNTAPPD ↗</span>
                                                <span className={group.rating ? "untappd-badge" : "untappd-badge na"}>
                                                    {group.rating ? Number(group.rating).toFixed(2) : "N/A"}
                                                </span>
                                            </a>
                                        ) : (
                                            <span className="na-text">N/A</span>
                                        )}
                                        {group.rating_count > 0 && <span className="rating-count">({group.rating_count})</span>}
                                    </div>
                                </td>
                                <td className="col-shop">
                                    <div className="shop-list-flat">
                                        {sortedItems.map((item, idx) => (
                                            <div key={idx} className="shop-item-flat">
                                                <a href={item.url} target="_blank" rel="noopener noreferrer" className="shop-btn-flat">
                                                    <div className="shop-info-primary">
                                                        <span className="price-text">{formatPrice(item.price)}</span>
                                                        <span className="shop-name-text">{item.shop}</span>
                                                        {item.stock_status && (
                                                            <span className={`stock-dot ${item.stock_status.toLowerCase().includes('out') ? 'out' : 'in'}`} title={item.stock_status}></span>
                                                        )}
                                                    </div>
                                                    <div className="shop-info-secondary">
                                                        {item.last_seen && <span className="check-date">{formatSimpleDate(item.last_seen)}</span>}
                                                        <span className="external-link-arrow">↗</span>
                                                    </div>
                                                </a>
                                            </div>
                                        ))}
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                    {groups.length === 0 && !loading && (
                        <tr>
                            <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                                No grouped beers found.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

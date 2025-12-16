import React from 'react'

export default function GroupedBeerTable({ groups, loading, error }) {

    const formatPrice = (price) => {
        if (!price) return '¥-';
        if (price.includes('¥')) return price;
        const num = parseInt(price.replace(/[^0-9]/g, ''), 10);
        if (isNaN(num)) return price;
        return new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'JPY' }).format(num);
    }

    const formatSimpleDate = (isoString) => {
        if (!isoString) return '-';
        // Safari fix: Replace space with T for ISO format
        const safeDate = isoString.replace(' ', 'T');
        try {
            const date = new Date(safeDate);
            if (isNaN(date.getTime())) return '-';
            return date.toLocaleDateString('ja-JP', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
            });
        } catch (e) {
            return '-';
        }
    }

    if (loading) return <div className="status-message">Loading grouped collection...</div>
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
                    {groups.map(group => {
                        // Sort items by price to find cheapest. Clone array to avoid mutating prop.
                        const sortedItems = [...(group.items || [])].sort((a, b) => (a.price_value || Infinity) - (b.price_value || Infinity));
                        const cheapestItem = sortedItems[0];
                        // Use cheapest item's image, fallback to group image
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
                                        {group.style ? (
                                            <span className="beer-style-text">{group.style}</span>
                                        ) : (
                                            <span className="na-text">Top Style N/A</span>
                                        )}
                                        <div className="stats-row">
                                            <div className="stat-item">
                                                {group.abv ? `${group.abv.toString().includes('%') ? Number(group.abv.replace('%', '')).toFixed(1) : Number(group.abv).toFixed(1)}% ABV` : <span className="na-text">N/A ABV</span>}
                                            </div>
                                            <span className="separator">•</span>
                                            <div className="stat-item">
                                                {group.ibu ? `${Number(group.ibu.toString().replace(/[^0-9.]/g, '')).toFixed(0)} IBU` : <span className="na-text">N/A IBU</span>}
                                            </div>
                                        </div>
                                    </div>
                                </td>
                                <td className="col-rating">
                                    <div className="rating-box">
                                        {group.untappd_url ? (
                                            <a href={group.untappd_url} target="_blank" rel="noopener noreferrer" className="untappd-badge-link">
                                                <span className="untappd-header">UNTAPPD ↗</span>
                                                {group.rating ? (
                                                    <span className="untappd-badge">{Number(group.rating).toFixed(2)}</span>
                                                ) : (
                                                    <span className="untappd-badge na">N/A</span>
                                                )}
                                            </a>
                                        ) : (
                                            <div className="untappd-badge-container">
                                                <span className="untappd-header">UNTAPPD</span>
                                                <span className="untappd-badge na">N/A</span>
                                            </div>
                                        )}
                                        {group.rating_count > 0 && (
                                            <span className="rating-count">({group.rating_count})</span>
                                        )}
                                        {group.untappd_updated_at && (
                                            <span className="fetched-date">{formatSimpleDate(group.untappd_updated_at)}</span>
                                        )}
                                    </div>
                                </td>
                                <td className="col-shop">
                                    <div className="shop-list-flat">
                                        {sortedItems.map((item, idx) => (
                                            <div key={idx} className="shop-item-flat">
                                                <a href={item.url} target="_blank" rel="noopener noreferrer" className="shop-btn-flat">
                                                    <div className="shop-info-primary">
                                                        <span className="price-text">
                                                            {formatPrice(item.price)}
                                                        </span>
                                                        <span className="shop-name-text">{item.shop}</span>
                                                        {item.stock_status && (
                                                            <span className={`stock-dot ${item.stock_status.toLowerCase().includes('out') ? 'out' : 'in'}`} title={item.stock_status}>
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div className="shop-info-secondary">
                                                        {item.last_seen && (
                                                            <span className="check-date">
                                                                {formatSimpleDate(item.last_seen)}
                                                            </span>
                                                        )}
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
                    {groups.length === 0 && (
                        <tr>
                            <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                                No grouped beers found matching your criteria.
                                <br />
                                <small>(Note: Only beers with Untappd data are shown in Grouped view)</small>
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

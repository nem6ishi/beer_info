import BeerInfoCell from './cells/BeerInfoCell';
import RatingCell from './cells/RatingCell';
import React from 'react'

import { formatPrice, formatSimpleDate } from './utils/formatters';

export default function GroupedBeerTable({ groups, loading, error }) {

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

                        // Image selection logic:
                        // 1. Untappd image if available and NOT default
                        // 2. Cheapest shop item image
                        // 3. Any shop item image
                        // 4. Placeholder (never show Untappd default)

                        let displayImage = group.beer_image;
                        const isDefaultUntappd = !displayImage || (displayImage && displayImage.includes('badge-beer-default'));

                        if (isDefaultUntappd) {
                            // Try cheapest first
                            if (cheapestItem && cheapestItem.image) {
                                displayImage = cheapestItem.image;
                            } else {
                                // Try finding ANY item with an image
                                const itemWithImage = sortedItems.find(i => i.image);
                                if (itemWithImage) {
                                    displayImage = itemWithImage.image;
                                } else {
                                    // No shop images found. Force placeholder/empty so we don't show the Untappd default.
                                    displayImage = ''; // This will trigger onError or show nothing, better than default
                                }
                            }
                        }

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
                                    <BeerInfoCell
                                        brewery={group.brewery}
                                        beer={(group.untappd_url && !group.untappd_url.includes('/search')) ? group.beer_name : (cheapestItem?.name || group.beer_name)}
                                        logo={group.brewery_logo}
                                        location={group.brewery_location}
                                        type={group.brewery_type}
                                    />
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
                                    {group.is_set ? (
                                        <div className="set-badge-container">
                                            <span className="set-badge">📦 Set Product</span>
                                        </div>
                                    ) : (
                                        <RatingCell
                                            rating={group.rating}
                                            count={group.rating_count}
                                            url={group.untappd_url}
                                        />
                                    )}
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

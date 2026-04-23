import BeerInfoCell from './cells/BeerInfoCell';
import RatingCell from './cells/RatingCell';
import React from 'react'
import BeerImage from './BeerImage'
import type { GroupedBeer } from '../types/beer'

import { formatPrice, formatSimpleDate } from './utils/formatters';

interface GroupedBeerTableProps {
    groups: GroupedBeer[];
    loading: boolean;
    error: string | null;
}

export default function GroupedBeerTable({ groups, loading, error }: GroupedBeerTableProps) {

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
                        // 2. Cheapest shop item image as fallback
                        
                        const untappdImg = group.beer_image;
                        const hasValidUntappd = untappdImg && !untappdImg.includes('badge-beer-default');
                        
                        const displayImage = hasValidUntappd ? untappdImg : (cheapestItem?.image || '');
                        const fallbackImage = hasValidUntappd ? (cheapestItem?.image || '') : '';

                        return (
                            <tr key={group.untappd_url || group.beer_name}>
                                <td className="col-img">
                                    <BeerImage 
                                        src={displayImage} 
                                        alt={group.beer_name} 
                                        fallbackSrc={fallbackImage}
                                    />
                                </td>
                                <td className="col-name">
                                    <BeerInfoCell
                                        brewery={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_name : null}
                                        beer={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.beer_name : (cheapestItem?.shop ? cheapestItem.shop : group.beer_name)}
                                        logo={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_logo : null}
                                        location={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_location : null}
                                        type={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_type : null}
                                        fallbackName={cheapestItem?.shop ? cheapestItem.shop : group.beer_name}
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
                                    {group.product_type === 'set' ? (
                                        <div className="set-badge-container">
                                            <span className="set-badge">📦 Set Product</span>
                                        </div>
                                    ) : group.product_type === 'glass' ? (
                                        <div className="set-badge-container">
                                            <span className="set-badge" style={{ background: '#17a2b8' }}>🍺 Glass</span>
                                        </div>
                                    ) : group.product_type === 'other' ? (
                                        <div className="set-badge-container">
                                            <span className="set-badge" style={{ background: '#6c757d' }}>📦 Other</span>
                                        </div>
                                    ) : (
                                        <RatingCell
                                            rating={group.rating}
                                            count={group.rating_count}
                                            url={group.untappd_url}
                                            productType={group.product_type}
                                            breweryName={group.brewery_name}
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
                            <td colSpan={5} style={{ textAlign: 'center', padding: '2rem' }}>
                                No grouped beers found.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

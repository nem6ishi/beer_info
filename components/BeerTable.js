import BeerInfoCell from './cells/BeerInfoCell';
import RatingCell from './cells/RatingCell';
import React from 'react'

import { formatPrice, formatSimpleDate } from './utils/formatters';

export default function BeerTable({ beers, loading, error }) {

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
                                <BeerInfoCell
                                    brewery={beer.untappd_brewery_name}
                                    beer={(beer.untappd_url && !beer.untappd_url.includes('/search')) ? beer.untappd_beer_name : beer.name}
                                    logo={beer.brewery_logo}
                                    location={beer.brewery_location}
                                    type={beer.brewery_type}
                                />
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
                                {beer.is_set ? (
                                    <div className="set-badge-container">
                                        <span className="set-badge">📦 Set Product</span>
                                    </div>
                                ) : (
                                    <RatingCell
                                        rating={beer.untappd_rating}
                                        count={beer.untappd_rating_count}
                                        url={beer.untappd_url}
                                    />
                                )}
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

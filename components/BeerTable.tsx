// Imports removed
import React from 'react'
import Image from 'next/image'
import type { Beer } from '../types/beer'
import BeerTableRow from './BeerTableRow';

import { formatPrice, formatSimpleDate } from './utils/formatters';

interface BeerTableProps {
    beers: Beer[];
    loading: boolean;
    error: string | null;
    isDebug?: boolean;
}

export default function BeerTable({ beers, loading, error, isDebug }: BeerTableProps) {

    if (error) return <div className="status-message error">Error: {error}</div>

    // Don't block render on loading. Show table with opacity if reloading.
    // If initial load and no data, show a simple loading message in a container to prevent CLS if possible, 
    // but here we prioritize simplicity.
    if (loading && beers.length === 0) {
        return <div className="status-message">Loading...</div>
    }

    const hasUntappdBeerData = (beer: Beer): boolean =>
        !!(beer.untappd_url && !beer.untappd_url.includes('/search') && beer.product_type === 'beer');

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
                    {beers.map(beer => {
                        const shopContent = (
                            <div className="shop-list-flat">
                                <a href={beer.url} target="_blank" rel="noopener noreferrer" className="shop-btn-flat">
                                    <div className="shop-info-primary">
                                        <span className="price-text">{formatPrice(beer.price)}</span>
                                        <span className="shop-name-text">{beer.shop}</span>
                                        {beer.stock_status && (
                                            <span className={`stock-dot ${beer.stock_status.toLowerCase().includes('out') ? 'out' : 'in'}`} title={beer.stock_status}></span>
                                        )}
                                    </div>
                                    <div className="shop-info-secondary">
                                        <span className="check-date">{formatSimpleDate(beer.last_seen)}</span>
                                        <span className="external-link-arrow">↗</span>
                                    </div>
                                </a>
                            </div>
                        );

                        return (
                            <BeerTableRow
                                key={beer.id || beer.url}
                                idKey={beer.id || beer.url}
                                imageSrc={beer.image}
                                imageFallbackSrc={beer.untappd_image || undefined}
                                altText={beer.name}
                                breweryName={hasUntappdBeerData(beer) ? beer.untappd_brewery_name : null}
                                beerName={hasUntappdBeerData(beer) ? beer.untappd_beer_name || beer.name : beer.name}
                                breweryLogo={hasUntappdBeerData(beer) ? beer.brewery_logo : null}
                                breweryLocation={hasUntappdBeerData(beer) ? beer.brewery_location : null}
                                breweryType={hasUntappdBeerData(beer) ? beer.brewery_type : null}
                                fallbackName={beer.name}
                                styleText={beer.untappd_style}
                                abv={beer.untappd_abv}
                                ibu={beer.untappd_ibu}
                                productType={beer.product_type}
                                rating={beer.untappd_rating}
                                ratingCount={beer.untappd_rating_count}
                                untappdUrl={beer.untappd_url}
                                shopContent={shopContent}
                                isDebug={isDebug}
                            />
                        );
                    })}
                    {beers.length === 0 && !loading && (
                        <tr>
                            <td colSpan={5} style={{ textAlign: 'center', padding: '2rem' }}>
                                No beers found.
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    )
}

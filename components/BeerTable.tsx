// Imports removed
import React from 'react'
import Image from 'next/image'
import type { Beer } from '../types/beer'
import BeerTableRow from './BeerTableRow';

import ShopCell from './ShopCell';
interface BeerTableProps {
    beers: Beer[];
    loading: boolean;
    error: string | null;
    isDebug?: boolean;
}

export default function BeerTable({ beers, loading, error, isDebug }: BeerTableProps) {

    if (error) return <div className="status-message error">Error: {error}</div>

    // Don't block render on loading. Show table with opacity if reloading.
    if (loading && beers.length === 0) {
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
                        {[...Array(5)].map((_, i) => (
                            <tr key={`skeleton-${i}`}>
                                <td className="col-img">
                                    <div className="skeleton skeleton-img"></div>
                                </td>
                                <td className="col-name">
                                    <div className="skeleton skeleton-text short"></div>
                                    <div className="skeleton skeleton-text"></div>
                                    <div className="skeleton skeleton-text medium"></div>
                                </td>
                                <td className="col-beer-style">
                                    <div className="skeleton skeleton-badge"></div>
                                    <div className="skeleton skeleton-text short" style={{marginTop: '8px'}}></div>
                                </td>
                                <td className="col-rating">
                                    <div className="skeleton skeleton-img" style={{width: '60px', height: '60px', borderRadius: '8px', margin: '0 auto'}}></div>
                                </td>
                                <td className="col-shop">
                                    <div className="skeleton skeleton-btn"></div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
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
                    {beers.map((beer, index) => {
                        const shopContent = (
                            <ShopCell 
                                url={beer.url}
                                price={beer.price}
                                shop={beer.shop}
                                stockStatus={beer.stock_status}
                                lastSeen={beer.last_seen}
                            />
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
                                firstSeen={beer.first_seen}
                                priority={index < 5}
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

import React from 'react'
import type { GroupedBeer } from '../types/beer'
import BeerTableRow from './BeerTableRow';

import { formatPrice, formatSimpleDate } from './utils/formatters';

interface GroupedBeerTableProps {
    groups: GroupedBeer[];
    loading: boolean;
    error: string | null;
    isDebug?: boolean;
    stockFilter?: string;
}

export default function GroupedBeerTable({ groups, loading, error, isDebug, stockFilter = 'in_stock' }: GroupedBeerTableProps) {

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
                    {groups.map((group, index) => {
                        const rawSorted = [...(group.items || [])].sort((a, b) => (a.price_value || Infinity) - (b.price_value || Infinity));
                        
                        const shopsWithInStock = new Set(
                            rawSorted
                                .filter(it => !it.stock_status?.toLowerCase().includes('out'))
                                .map(it => it.shop)
                        );

                        const latestSoldOutUrlPerShop = new Map<string, string>();
                        rawSorted.forEach(it => {
                            const isSoldOut = it.stock_status?.toLowerCase().includes('out');
                            if (isSoldOut && !shopsWithInStock.has(it.shop)) {
                                const currentLatestUrl = latestSoldOutUrlPerShop.get(it.shop);
                                if (!currentLatestUrl) {
                                    latestSoldOutUrlPerShop.set(it.shop, it.url);
                                } else {
                                    const exItem = rawSorted.find(r => r.url === currentLatestUrl);
                                    const dtNew = new Date(it.last_seen || 0).getTime();
                                    const dtOld = new Date(exItem?.last_seen || 0).getTime();
                                    if (dtNew > dtOld) {
                                        latestSoldOutUrlPerShop.set(it.shop, it.url);
                                    }
                                }
                            }
                        });

                        const seenUrls = new Set<string>();
                        const sortedItems = rawSorted.filter(item => {
                            if (!item.url || seenUrls.has(item.url)) return false;
                            seenUrls.add(item.url);

                            const isSoldOut = item.stock_status?.toLowerCase().includes('out');
                            if (stockFilter === 'in_stock' && isSoldOut) return false;
                            if (stockFilter === 'sold_out' && !isSoldOut) return false;

                            if (isSoldOut) {
                                if (shopsWithInStock.has(item.shop)) {
                                    return false;
                                }
                                if (latestSoldOutUrlPerShop.get(item.shop) !== item.url) {
                                    return false;
                                }
                            }
                            return true;
                        });
                        if (sortedItems.length === 0) return null;
                        const cheapestItem = sortedItems[0] || rawSorted[0];

                        // Image selection logic:
                        // 1. Untappd image if available and NOT default
                        // 2. Cheapest shop item image as fallback
                        
                        const untappdImg = group.beer_image;
                        const hasValidUntappd = untappdImg && !untappdImg.includes('badge-beer-default');
                        
                        const displayImage = hasValidUntappd ? untappdImg : (cheapestItem?.image || '');
                        const fallbackImage = hasValidUntappd ? (cheapestItem?.image || '') : '';

                        const shopContent = (
                            <div className="shop-list-flat">
                                {sortedItems.map((item, idx) => {
                                    const isSoldOut = item.stock_status?.toLowerCase().includes('out');

                                    return (
                                        <div key={idx} className="shop-item-flat">
                                            <a href={item.url} target="_blank" rel="noopener noreferrer" className={`shop-btn-flat ${isSoldOut ? 'sold-out-shop' : ''}`}>
                                                <div className="shop-info-primary">
                                                    <span className="price-text">{formatPrice(item.price)}</span>
                                                    <span className="shop-name-text">{item.shop}</span>
                                                    {item.stock_status && (
                                                        <span className={`stock-dot ${isSoldOut ? 'out' : 'in'}`} title={item.stock_status}></span>
                                                    )}
                                                </div>
                                                <div className="shop-info-secondary">
                                                    {item.last_seen && <span className="check-date">{formatSimpleDate(item.last_seen)}</span>}
                                                    <span className="external-link-arrow">↗</span>
                                                </div>
                                            </a>
                                        </div>
                                    );
                                })}
                            </div>
                        );

                        return (
                            <BeerTableRow
                                key={group.untappd_url || group.beer_name}
                                idKey={group.untappd_url || group.beer_name}
                                imageSrc={displayImage}
                                imageFallbackSrc={fallbackImage}
                                altText={group.beer_name}
                                breweryName={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_name : null}
                                beerName={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.beer_name : (cheapestItem?.shop ? cheapestItem.shop : group.beer_name)}
                                breweryLogo={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_logo : null}
                                breweryLocation={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_location : null}
                                breweryType={(group.untappd_url && !group.untappd_url.includes('/search') && group.product_type === 'beer') ? group.brewery_type : null}
                                fallbackName={cheapestItem?.shop ? cheapestItem.shop : group.beer_name}
                                styleText={group.style}
                                abv={group.abv}
                                ibu={group.ibu}
                                productType={group.product_type}
                                rating={group.rating}
                                ratingCount={group.rating_count}
                                untappdUrl={group.untappd_url}
                                shopContent={shopContent}
                                isDebug={isDebug}
                                firstSeen={group.newest_seen}
                                isSale={group.is_sale}
                                saleTag={group.sale_tag}
                                expiryNotice={group.expiry_notice}
                                priority={index < 5}
                            />
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

import React from 'react';
import { formatPrice, formatSimpleDate } from './utils/formatters';

interface ShopCellProps {
    url: string;
    price: number | string;
    shop: string;
    stockStatus?: string | null;
    lastSeen: string;
}

export default function ShopCell({ url, price, shop, stockStatus, lastSeen }: ShopCellProps) {
    const isSoldOut = stockStatus?.toLowerCase().includes('out');

    return (
        <div className="shop-list-flat">
            <a href={url} target="_blank" rel="noopener noreferrer" className={`shop-btn-flat ${isSoldOut ? 'sold-out-shop' : ''}`}>
                <div className="shop-info-primary">
                    <span className="price-text">{formatPrice(price as string)}</span>
                    <span className="shop-name-text">{shop}</span>
                    {stockStatus && (
                        <span className={`stock-dot ${isSoldOut ? 'out' : 'in'}`} title={stockStatus}></span>
                    )}
                </div>
                <div className="shop-info-secondary">
                    <span className="check-date">{formatSimpleDate(lastSeen)}</span>
                    <span className="external-link-arrow">↗</span>
                </div>
            </a>
        </div>
    );
}

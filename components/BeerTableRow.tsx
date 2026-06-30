import React, { ReactNode } from 'react';
import BeerImage from './BeerImage';
import BeerInfoCell from './cells/BeerInfoCell';
import RatingCell from './cells/RatingCell';

export interface BeerTableRowProps {
    idKey: string;
    
    // Image
    imageSrc: string | null | undefined;
    imageFallbackSrc?: string;
    altText: string;

    // Info
    breweryName: string | null;
    beerName: string;
    breweryLogo: string | null;
    breweryLocation: string | null;
    breweryType: string | null;
    fallbackName: string;

    // Style / Specs
    styleText: string | null;
    abv: number | null;
    ibu: number | null;

    // Rating
    productType: string | null;
    rating: number | null;
    ratingCount: number | null;
    untappdUrl: string | null;

    // Shop availability content (varies between list and grouped)
    shopContent: ReactNode;

    // Debug
    isDebug?: boolean;
    firstSeen?: string | null;

    // Performance
    priority?: boolean;
}

export default function BeerTableRow({
    idKey,
    imageSrc,
    imageFallbackSrc,
    altText,
    breweryName,
    beerName,
    breweryLogo,
    breweryLocation,
    breweryType,
    fallbackName,
    styleText,
    abv,
    ibu,
    productType,
    rating,
    ratingCount,
    untappdUrl,
    shopContent,
    isDebug,
    firstSeen,
    priority = false
}: BeerTableRowProps) {
    return (
        <tr key={idKey}>
            <td className="col-img">
                <BeerImage 
                    src={imageSrc} 
                    alt={altText} 
                    fallbackSrc={imageFallbackSrc} 
                    priority={priority}
                />
            </td>
            <td className="col-name">
                <BeerInfoCell
                    brewery={breweryName}
                    beer={beerName}
                    logo={breweryLogo}
                    location={breweryLocation}
                    type={breweryType}
                    fallbackName={fallbackName}
                    isDebug={isDebug}
                    firstSeen={firstSeen}
                />
            </td>
            <td className="col-beer-style">
                <div className="style-specs-group">
                    <span className={styleText ? "beer-style-text" : "na-text"}>
                        {styleText || 'Style N/A'}
                    </span>
                    <div className="stats-row">
                        <div className="stat-item">
                            {abv ? `${abv}% ABV` : <span className="na-text">N/A ABV</span>}
                        </div>
                        <span className="separator">•</span>
                        <div className="stat-item">
                            {ibu ? `${ibu} IBU` : <span className="na-text">N/A IBU</span>}
                        </div>
                    </div>
                </div>
            </td>
            <td className="col-rating">
                {productType === 'set' ? (
                    <div className="set-badge-container">
                        <span className="set-badge">📦 Set Product</span>
                    </div>
                ) : productType === 'glass' ? (
                    <div className="set-badge-container">
                        <span className="set-badge" style={{ background: '#17a2b8' }}>🍺 Glass</span>
                    </div>
                ) : productType === 'other' ? (
                    <div className="set-badge-container">
                        <span className="set-badge" style={{ background: '#6c757d' }}>📦 Other</span>
                    </div>
                ) : (
                    <RatingCell
                        rating={rating}
                        count={ratingCount}
                        url={untappdUrl}
                        productType={productType}
                        breweryName={breweryName}
                    />
                )}
            </td>
            <td className="col-shop">
                {shopContent}
            </td>
        </tr>
    );
}

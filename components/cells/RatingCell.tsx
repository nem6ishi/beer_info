import React from 'react';

interface RatingCellProps {
    rating: number | null;
    count: number | null;
    url: string | null;
    productType: string | null;
    breweryName?: string | null;
}

export default function RatingCell({ rating, count, url, productType }: RatingCellProps) {
    const displayRating = rating
        ? (typeof rating === 'number' ? rating.toFixed(2) : Number(rating).toFixed(2))
        : 'N/A';

    const validUrl = url && !url.includes('/search?q=') ? url : null;

    return (
        <div className="rating-box">
            {validUrl ? (
                <a href={validUrl} target="_blank" rel="noopener noreferrer" className="untappd-badge-link">
                    <span className="untappd-header">UNTAPPD ↗</span>
                    <span className="untappd-badge">
                        {displayRating}
                    </span>
                </a>
            ) : (
                rating ? (
                    <div className="untappd-badge-link" style={{ cursor: 'default' }}>
                        <span className="untappd-header">UNTAPPD</span>
                        <span className="untappd-badge">{displayRating}</span>
                    </div>
                ) : (
                    <span className="na-text">N/A</span>
                )
            )}
            {count != null && count > 0 && <span className="rating-count">({count})</span>}
        </div>
    );
}

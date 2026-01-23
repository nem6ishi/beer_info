import React from 'react';

export default function RatingCell({ rating, count, url, breweryName }) {
    const displayRating = rating
        ? (typeof rating === 'number' ? rating.toFixed(2) : Number(rating).toFixed(2))
        : 'N/A';

    const validUrl = url && !url.includes('/search?q=') ? url : null;

    // If no brewery name, it's likely a non-beer product (goods, merchandise, etc.)
    const isOthers = !breweryName && !rating;

    return (
        <div className="rating-box">
            {isOthers ? (
                <div className="set-badge-container">
                    <span className="set-badge" style={{ background: '#6c757d' }}>📦 Others</span>
                </div>
            ) : validUrl ? (
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
            {count > 0 && <span className="rating-count">({count})</span>}
        </div>
    );
}

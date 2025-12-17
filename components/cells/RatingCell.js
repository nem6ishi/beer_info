import React from 'react';

export default function RatingCell({ rating, count, url }) {
    return (
        <div className="rating-box">
            {rating ? (
                <a href={url || '#'} target="_blank" rel="noopener noreferrer" className="untappd-badge-link">
                    <span className="untappd-header">UNTAPPD ↗</span>
                    <span className="untappd-badge">
                        {typeof rating === 'number' ? rating.toFixed(2) : Number(rating).toFixed(2)}
                    </span>
                </a>
            ) : (
                <span className="na-text">N/A</span>
            )}
            {count > 0 && <span className="rating-count">({count})</span>}
        </div>
    );
}

import React from 'react';

interface RatingCellProps {
    rating: number | null;
    count: number | null;
    url: string | null;
    productType: string | null;
    breweryName?: string | null;
    enrichedAt?: string | null;
}

function formatEnrichedDate(isoString?: string | null): string | null {
    if (!isoString) return null;
    try {
        const date = new Date(isoString.replace(' ', 'T'));
        if (isNaN(date.getTime())) return null;
        const y = date.getFullYear();
        const m = (date.getMonth() + 1).toString().padStart(2, '0');
        const d = date.getDate().toString().padStart(2, '0');
        return `${y}/${m}/${d}時点`;
    } catch {
        return null;
    }
}

export default function RatingCell({ rating, count, url, productType, enrichedAt }: RatingCellProps) {
    const displayRating = rating
        ? (typeof rating === 'number' ? rating.toFixed(2) : Number(rating).toFixed(2))
        : 'N/A';

    const validUrl = url && !url.includes('/search?q=') ? url : null;
    const enrichedDateText = formatEnrichedDate(enrichedAt);

    return (
        <div className="rating-box">
            {validUrl ? (
                <a href={validUrl} target="_blank" rel="noopener noreferrer" className="untappd-badge-link" title="Untappdで開く">
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
                    <div 
                        className="untappd-badge-container" 
                        title={enrichedDateText ? `Untappd未登録のアイテムです (${enrichedDateText})` : "Untappd未登録のアイテムです"}
                    >
                        <span className="untappd-header">UNTAPPD</span>
                        <span className="untappd-badge unlisted">未登録</span>
                        {enrichedDateText && (
                            <span className="unlisted-date">{enrichedDateText}</span>
                        )}
                    </div>
                )
            )}
            {count != null && count > 0 && <span className="rating-count">({count})</span>}
        </div>
    );
}

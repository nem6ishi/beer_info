import React from 'react';

const COUNTRY_FLAGS: Record<string, string> = {
    'United States': '🇺🇸',
    'Japan': '🇯🇵',
    'Belgium': '🇧🇪',
    'Germany': '🇩🇪',
    'United Kingdom': '🇬🇧',
    'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'Scotland': '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    'Wales': '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
    'Ireland': '🇮🇪',
    'France': '🇫🇷',
    'Italy': '🇮🇹',
    'Spain': '🇪🇸',
    'Netherlands': '🇳🇱',
    'Sweden': '🇸🇪',
    'Denmark': '🇩🇰',
    'Norway': '🇳🇴',
    'Canada': '🇨🇦',
    'Australia': '🇦🇺',
    'New Zealand': '🇳🇿',
    'China': '🇨🇳',
    'South Korea': '🇰🇷',
    'Republic of Korea': '🇰🇷',
    'Hong Kong': '🇭🇰',
    'Taiwan': '🇹🇼',
    'Poland': '🇵🇱',
    'Estonia': '🇪🇪',
    'Latvia': '🇱🇻',
    'Czech Republic': '🇨🇿',
    'Switzerland': '🇨🇭',
    'Austria': '🇦🇹',
};

function getFlag(location: string | null): string | null {
    if (!location) return null;
    for (const [country, flag] of Object.entries(COUNTRY_FLAGS)) {
        if (location.endsWith(country)) {
            return flag;
        }
    }
    return null;
}

function isRecent(dateStr?: string | null): boolean {
    if (!dateStr) return false;
    const dt = new Date(dateStr);
    const now = new Date();
    const diffHours = (now.getTime() - dt.getTime()) / (1000 * 60 * 60);
    return diffHours >= 0 && diffHours <= 72;
}

interface BeerInfoCellProps {
    brewery: string | null;
    beer: string | null;
    logo: string | null;
    location: string | null;
    type: string | null;
    fallbackName: string;
    isDebug?: boolean;
    firstSeen?: string | null;
}

export default function BeerInfoCell({ brewery, beer, logo, location, type, fallbackName, isDebug, firstSeen }: BeerInfoCellProps) {
    const flag = getFlag(location);

    // Use beer name if available, otherwise use fallback (original product name)
    const displayName = beer || fallbackName || 'Beer name not available';

    return (
        <div className="beer-name-group">
            {brewery && (
                <div className="brewery-row" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                    {logo && (
                        <img
                            src={logo}
                            alt={brewery}
                            style={{ width: '24px', height: '24px', borderRadius: '4px', objectFit: 'contain' }}
                            loading="lazy"
                        />
                    )}
                    <div className="brewery-info" style={{ lineHeight: '1.2' }}>
                        <div className="brewery-name" style={{ fontWeight: 'bold' }}>
                            {brewery}
                        </div>
                        {location && (
                            <div className="brewery-meta" style={{ fontSize: '0.75rem', color: '#666' }}>
                                {location} {flag && <span style={{ marginLeft: '4px' }}>{flag}</span>}
                            </div>
                        )}
                    </div>
                </div>
            )}
            <div className="beer-name" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                <span>{displayName}</span>
                {isRecent(firstSeen) && (
                    <span style={{
                        background: 'linear-gradient(135deg, #ff416c, #ff4b2b)',
                        color: 'white',
                        fontSize: '0.65rem',
                        fontWeight: 'bold',
                        padding: '2px 6px',
                        borderRadius: '12px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        boxShadow: '0 2px 4px rgba(255, 75, 43, 0.3)'
                    }}>NEW</span>
                )}
            </div>
            {isDebug && beer && fallbackName && beer !== fallbackName && (
                <div className="debug-original-name" style={{ fontSize: '0.8rem', color: '#ff6b6b', marginTop: '4px', fontFamily: 'monospace' }}>
                    [Original]: {fallbackName}
                </div>
            )}
        </div>
    );
}


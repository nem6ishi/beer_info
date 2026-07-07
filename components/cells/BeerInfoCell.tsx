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
    return diffHours >= 0 && diffHours <= 24;
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
    isSale?: boolean | null;
    saleTag?: string | null;
    expiryNotice?: string | null;
}

export default function BeerInfoCell({ brewery, beer, logo, location, type, fallbackName, isDebug, firstSeen, isSale, saleTag, expiryNotice }: BeerInfoCellProps) {
    const flag = getFlag(location);

    // Fallback extraction from fallbackName (raw title) if DB columns aren't populated yet
    const rawTitle = fallbackName || '';
    const computedSaleTag = saleTag || (() => {
        const match = rawTitle.match(/([0-9.]+%\s*OFF|SALE!*|セール|最終特価|特価|アウトレット|訳あり|決算セール|在庫整理|お試しセット)/i);
        return match ? match[1] : null;
    })();
    const computedExpiry = expiryNotice || (() => {
        const match = rawTitle.match(/((?:賞味)?期限[^】\)]+)/);
        return match ? match[1] : null;
    })();
    const computedIsSale = isSale !== undefined && isSale !== null ? isSale : (!!computedSaleTag || !!computedExpiry || /OFF|SALE|セール|特価|訳あり|賞味期限/i.test(rawTitle));

    // Use beer name if available, otherwise use fallback (original product name)
    const rawDisplayName = beer || fallbackName || 'Beer name not available';
    const displayName = rawDisplayName.replace(/^([0-9.]+%\s*OFF|SALE!*|セール|最終特価|特価|アウトレット|訳あり|決算セール|在庫整理|お試しセット)\s*/i, '').trim() || rawDisplayName;
    const recent = isRecent(firstSeen);

    const badgeStyle: React.CSSProperties = {
        display: 'inline-block',
        background: 'linear-gradient(135deg, #ff416c, #ff4b2b)',
        color: 'white',
        fontSize: '0.65rem',
        fontWeight: 'bold',
        padding: '1px 6px',
        borderRadius: '10px',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
        boxShadow: '0 2px 4px rgba(255, 75, 43, 0.3)',
        marginLeft: '6px',
        verticalAlign: 'middle',
        whiteSpace: 'nowrap'
    };

    const saleBadgeStyle: React.CSSProperties = {
        display: 'inline-block',
        background: 'linear-gradient(135deg, #ff0844, #ffb199)',
        color: 'white',
        fontSize: '0.68rem',
        fontWeight: '800',
        padding: '2px 7px',
        borderRadius: '12px',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
        boxShadow: '0 2px 6px rgba(255, 8, 68, 0.35)',
        marginLeft: '6px',
        verticalAlign: 'middle',
        whiteSpace: 'nowrap'
    };

    const expiryBadgeStyle: React.CSSProperties = {
        display: 'inline-block',
        background: 'linear-gradient(135deg, #f6d365, #fda085)',
        color: '#7c3f00',
        fontSize: '0.65rem',
        fontWeight: 'bold',
        padding: '1px 6px',
        borderRadius: '10px',
        marginLeft: '6px',
        verticalAlign: 'middle',
        whiteSpace: 'nowrap'
    };

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
            <div className="beer-name" style={{ lineHeight: '1.4', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '4px' }}>
                <span>
                    {recent ? (
                        (() => {
                            const words = displayName.trim().split(' ');
                            if (words.length <= 1) {
                                return (
                                    <span style={{ whiteSpace: 'nowrap' }}>
                                        {displayName}
                                        <span style={badgeStyle}>NEW</span>
                                    </span>
                                );
                            }
                            const lastWord = words.pop();
                            const firstPart = words.join(' ') + ' ';
                            return (
                                <>
                                    {firstPart}
                                    <span style={{ whiteSpace: 'nowrap' }}>
                                        {lastWord}
                                        <span style={badgeStyle}>NEW</span>
                                    </span>
                                </>
                            );
                        })()
                    ) : (
                        displayName
                    )}
                </span>
                {computedSaleTag && (
                    <span style={saleBadgeStyle}>🔥 {computedSaleTag}</span>
                )}
                {computedIsSale && !computedSaleTag && (
                    <span style={saleBadgeStyle}>🔥 SALE</span>
                )}
                {computedExpiry && (
                    <span style={expiryBadgeStyle}>⏳ {computedExpiry}</span>
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


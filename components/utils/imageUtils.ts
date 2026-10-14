/**
 * Utility functions for image handling and optimization
 */

export const DEFAULT_BEER_PLACEHOLDER = 'https://placehold.co/100x100?text=No+Image';

export function isDefaultUntappd(url: string): boolean {
    if (!url) return false;
    return (
        url.includes('badge-beer-default') ||
        url.includes('no_image') ||
        url.includes('placeholder') ||
        url.includes('next.untappd.com/og/')
    );
}

/**
 * Transforms an image URL into a fast, compressed WebP thumbnail via wsrv.nl CDN.
 * Fits within 180x180 (for 90px @ 2x Retina screens) with fit=contain to preserve aspect ratio.
 */
export function toThumbnailUrl(url?: string | null, width = 180, height = 180): string | null {
    if (!url) return null;
    if (isDefaultUntappd(url)) return null;

    // Do not proxy data URLs, placehold.co, or already proxied URLs
    if (url.startsWith('data:') || url.includes('placehold.co') || url.includes('wsrv.nl')) {
        return url;
    }

    // Only proxy absolute http/https URLs
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        return url;
    }

    try {
        // wsrv.nl expects ?url=...
        return `https://wsrv.nl/?url=${encodeURIComponent(url)}&w=${width}&h=${height}&fit=contain&output=webp`;
    } catch {
        return url;
    }
}

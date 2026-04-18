import React, { useState } from 'react'
import Image from 'next/image'

interface BeerImageProps {
    src?: string | null;
    alt: string;
    fallbackSrc?: string;
    width?: number;
    height?: number;
    className?: string;
}

const BeerImage: React.FC<BeerImageProps> = ({ 
    src, 
    alt, 
    fallbackSrc, 
    width = 64, 
    height = 64,
    className = "beer-image"
}) => {
    const defaultPlaceholder = 'https://placehold.co/100x100?text=No+Image';
    const [imgSrc, setImgSrc] = useState<string>(src || fallbackSrc || defaultPlaceholder);
    const [isLoaded, setIsLoaded] = useState(false);
    const [hasError, setHasError] = useState(false);

    const isDefaultUntappd = (url: string) => 
        url.includes('badge-beer-default') || 
        url.includes('no_image') || 
        url.includes('placeholder');

    React.useEffect(() => {
        const primary = src && !isDefaultUntappd(src) ? src : (fallbackSrc && !isDefaultUntappd(fallbackSrc) ? fallbackSrc : defaultPlaceholder);
        setImgSrc(primary);
    }, [src, fallbackSrc]);

    return (
        <div 
            className={`beer-image-container ${isLoaded ? 'loaded' : 'loading'}`} 
            style={{ 
                width, 
                height, 
                position: 'relative', 
                overflow: 'hidden', 
                borderRadius: '8px', 
                background: '#f8f9fa',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
            }}
        >
            <Image
                src={imgSrc}
                alt={alt}
                width={width}
                height={height}
                className={className}
                onLoad={() => setIsLoaded(true)}
                onError={() => {
                    if (!hasError) {
                        setHasError(true);
                        if (fallbackSrc && imgSrc !== fallbackSrc) {
                            setImgSrc(fallbackSrc);
                        } else {
                            setImgSrc(defaultPlaceholder);
                        }
                    } else {
                        setImgSrc(defaultPlaceholder);
                    }
                }}
                unoptimized={imgSrc.startsWith('http') && !imgSrc.includes('googleusercontent') && !imgSrc.includes('akamaized')} // Partially bypass proxy for problematic ones if needed, but for now let's hope remotePatterns works
                style={{ 
                    objectFit: 'contain',
                    maxWidth: '100%',
                    maxHeight: '100%',
                    opacity: isLoaded ? 1 : 0,
                    transition: 'opacity 0.2s ease-in-out'
                }}
            />
            {!isLoaded && !hasError && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div className="spinner-small" style={{ width: '16px', height: '16px', border: '2px solid #ddd', borderTopColor: '#666', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
                </div>
            )}
        </div>
    )
}

export default BeerImage;

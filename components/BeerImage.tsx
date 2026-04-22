import React, { useState } from 'react'
import Image from 'next/image'

interface BeerImageProps {
    src?: string | null;
    alt: string;
    fallbackSrc?: string;
    className?: string;
}

const BeerImage: React.FC<BeerImageProps> = ({ 
    src, 
    alt, 
    fallbackSrc, 
    className = ""
}) => {
    const defaultPlaceholder = 'https://placehold.co/100x100?text=No+Image';
    
    const isDefaultUntappd = (url: string) => 
        url.includes('badge-beer-default') || 
        url.includes('no_image') || 
        url.includes('placeholder');

    const getPrimarySrc = () => {
        if (src && !isDefaultUntappd(src)) return src;
        if (fallbackSrc && !isDefaultUntappd(fallbackSrc)) return fallbackSrc;
        return defaultPlaceholder;
    };

    const [imgSrc, setImgSrc] = useState<string>(getPrimarySrc());
    const [isLoaded, setIsLoaded] = useState(false);
    const [hasError, setHasError] = useState(false);

    React.useEffect(() => {
        setImgSrc(getPrimarySrc());
        setIsLoaded(false);
        setHasError(false);
    }, [src, fallbackSrc]);

    return (
        <div 
            className={`beer-image-wrapper ${isLoaded ? 'loaded' : 'loading'} ${className}`} 
            style={{ 
                position: 'relative'
            }}
        >
            <Image
                src={imgSrc}
                alt={alt}
                fill
                sizes="(max-width: 768px) 80px, 90px"
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

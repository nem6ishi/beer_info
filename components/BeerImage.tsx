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

    // Initial check for default Untappd images which we want to skip if possible
    const isDefaultUntappd = (url: string) => url.includes('badge-beer-default');

    React.useEffect(() => {
        if (!src && !fallbackSrc) {
            setImgSrc(defaultPlaceholder);
        } else {
            setImgSrc(src || fallbackSrc || defaultPlaceholder);
        }
    }, [src, fallbackSrc]);

    return (
        <div className={`beer-image-container ${isLoaded ? 'loaded' : 'loading'}`} style={{ width, height, position: 'relative', overflow: 'hidden', borderRadius: '8px', background: '#f0f0f0' }}>
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
                unoptimized={imgSrc.startsWith('data:')} // Optimization: unoptimized for data URLs if any
                style={{ objectFit: 'cover' }}
            />
        </div>
    )
}

export default BeerImage;

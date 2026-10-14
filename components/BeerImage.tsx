import React, { useState, useEffect, useMemo } from 'react'
import Image from 'next/image'
import { DEFAULT_BEER_PLACEHOLDER, isDefaultUntappd, toThumbnailUrl } from './utils/imageUtils'

interface BeerImageProps {
    src?: string | null;
    alt: string;
    fallbackSrc?: string;
    className?: string;
    priority?: boolean;
}

const BeerImage: React.FC<BeerImageProps> = ({ 
    src, 
    alt, 
    fallbackSrc, 
    className = "",
    priority = false
}) => {
    // Determine the sequence of candidate URLs to try in order of preference
    const candidates = useMemo(() => {
        const list: string[] = [];

        const validSrc = src && !isDefaultUntappd(src) ? src : null;
        const validFallback = fallbackSrc && !isDefaultUntappd(fallbackSrc) ? fallbackSrc : null;

        if (validSrc) {
            const thumb = toThumbnailUrl(validSrc);
            if (thumb && thumb !== validSrc) list.push(thumb);
            list.push(validSrc);
        }

        if (validFallback) {
            const thumbFallback = toThumbnailUrl(validFallback);
            if (thumbFallback && thumbFallback !== validFallback) list.push(thumbFallback);
            list.push(validFallback);
        }

        list.push(DEFAULT_BEER_PLACEHOLDER);
        return list;
    }, [src, fallbackSrc]);

    const [candidateIndex, setCandidateIndex] = useState(0);
    const [isLoaded, setIsLoaded] = useState(false);

    // Reset when candidates change
    useEffect(() => {
        setCandidateIndex(0);
        setIsLoaded(false);
    }, [candidates]);

    const currentSrc = candidates[candidateIndex] || DEFAULT_BEER_PLACEHOLDER;

    const handleError = () => {
        if (candidateIndex < candidates.length - 1) {
            setCandidateIndex(prev => prev + 1);
        }
    };

    return (
        <div 
            className={`beer-image-wrapper ${isLoaded ? 'loaded' : 'loading'} ${className}`} 
            style={{ 
                position: 'relative'
            }}
        >
            <Image
                src={currentSrc}
                alt={alt}
                fill
                priority={priority}
                loading={priority ? undefined : 'lazy'}
                sizes="(max-width: 768px) 80px, 90px"
                onLoad={() => setIsLoaded(true)}
                onError={handleError}
                unoptimized={true}
                style={{ 
                    objectFit: 'contain',
                    opacity: isLoaded ? 1 : 0,
                    transition: 'opacity 0.15s ease-out'
                }}
            />
        </div>
    )
}

export default BeerImage;

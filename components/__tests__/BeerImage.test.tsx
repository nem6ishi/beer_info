import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import BeerImage from '../BeerImage'
import { toThumbnailUrl, DEFAULT_BEER_PLACEHOLDER } from '../utils/imageUtils'

describe('toThumbnailUrl', () => {
    it('creates a wsrv.nl proxy URL for valid http/https URLs', () => {
        const original = 'https://example.com/beer.jpg'
        const thumb = toThumbnailUrl(original)
        expect(thumb).toBe(`https://wsrv.nl/?url=${encodeURIComponent(original)}&w=180&h=180&fit=contain&output=webp`)
    })

    it('returns null for default placeholder or untappd badges', () => {
        expect(toThumbnailUrl('https://untappd.akamaized.net/site/assets/images/temp/badge-beer-default.png')).toBeNull()
        expect(toThumbnailUrl(null)).toBeNull()
        expect(toThumbnailUrl('')).toBeNull()
    })

    it('does not proxy data URLs or placehold.co URLs', () => {
        const dataUrl = 'data:image/png;base64,xxxx'
        expect(toThumbnailUrl(dataUrl)).toBe(dataUrl)
        expect(toThumbnailUrl(DEFAULT_BEER_PLACEHOLDER)).toBe(DEFAULT_BEER_PLACEHOLDER)
    })
})

describe('BeerImage Component', () => {
    it('renders with proxied thumbnail URL initially', () => {
        const original = 'https://example.com/beer.jpg'
        render(<BeerImage src={original} alt="Test Beer" />)
        const img = screen.getByRole('img')
        expect(img).toHaveAttribute('src', expect.stringContaining('wsrv.nl'))
    })

    it('falls back to original src if proxy thumbnail errors', () => {
        const original = 'https://example.com/beer.jpg'
        render(<BeerImage src={original} alt="Test Beer" />)
        const img = screen.getByRole('img')
        
        // Trigger error on thumbnail
        fireEvent.error(img)
        expect(img).toHaveAttribute('src', original)
    })

    it('falls back to fallbackSrc and then placeholder if all fail', () => {
        const original = 'https://example.com/beer.jpg'
        const fallback = 'https://example.com/fallback.jpg'
        render(<BeerImage src={original} fallbackSrc={fallback} alt="Test Beer" />)
        const img = screen.getByRole('img')

        // 1. thumbnail of src fails -> original src
        fireEvent.error(img)
        expect(img).toHaveAttribute('src', original)

        // 2. original src fails -> thumbnail of fallback
        fireEvent.error(img)
        expect(img).toHaveAttribute('src', expect.stringContaining('fallback.jpg'))

        // 3. thumbnail of fallback fails -> original fallback
        fireEvent.error(img)
        expect(img).toHaveAttribute('src', fallback)

        // 4. original fallback fails -> placeholder
        fireEvent.error(img)
        expect(img).toHaveAttribute('src', DEFAULT_BEER_PLACEHOLDER)
    })
})

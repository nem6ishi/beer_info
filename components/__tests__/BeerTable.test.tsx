import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import BeerTable from '../BeerTable';
import type { Beer } from '../../types/beer';

describe('BeerTable (Individual Display Table Tests)', () => {
    const mockBeers: Beer[] = [
        {
            url: 'https://beervolta.example.com/item/1',
            name: 'Shiga Kogen Sake IPA',
            price: '800円',
            price_value: 800,
            image: 'https://beervolta.example.com/img1.jpg',
            stock_status: 'In Stock',
            shop: 'BeerVolta',
            first_seen: '2026-07-01T00:00:00Z',
            last_seen: '2026-07-14T00:00:00Z',
            untappd_url: 'https://untappd.com/b/shiga-kogen-sake-ipa/12345',
            is_sale: false,
            sale_tag: null,
            expiry_notice: null,
            brewery_name_en: 'Shiga Kogen',
            brewery_name_jp: '志賀高原ビール',
            beer_name_en: 'Sake IPA',
            beer_name_jp: null,
            product_type: 'beer',
            is_set: false,
            untappd_beer_name: 'ENGI!? Sake IPA',
            untappd_brewery_name: 'Shiga Kogen Beer',
            untappd_style: 'IPA - Sake / Rice',
            untappd_abv: 7.5,
            untappd_ibu: 55,
            untappd_rating: 4.15,
            untappd_rating_count: 320,
            untappd_image: 'https://untappd.example.com/label.jpg',
            untappd_brewery_url: 'https://untappd.com/w/shiga-kogen/111',
            untappd_fetched_at: '2026-07-12T00:00:00Z',
            brewery_location: 'Nagano, Japan',
            brewery_type: 'Micro Brewery',
            brewery_logo: 'https://untappd.example.com/brewery-logo.jpg',
            brewery_id: 'shiga-kogen'
        }
    ];

    it('should display error message when error prop is passed', () => {
        render(<BeerTable beers={[]} loading={false} error="Refresh failed" />);
        expect(screen.getByText('Error: Refresh failed')).toBeDefined();
    });

    it('should display loading skeletons when loading is true and beers is empty', () => {
        const { container } = render(<BeerTable beers={[]} loading={true} error={null} />);
        expect(container.querySelectorAll('.skeleton').length).toBeGreaterThan(0);
    });

    it('should display empty message when not loading and beers array is empty', () => {
        render(<BeerTable beers={[]} loading={false} error={null} />);
        expect(screen.getByText('No beers found.')).toBeDefined();
    });

    it('should render individual beer row and shop availability cleanly', () => {
        render(<BeerTable beers={mockBeers} loading={false} error={null} />);
        expect(screen.getByText('ENGI!? Sake IPA')).toBeDefined();
        expect(screen.getByText('Shiga Kogen Beer')).toBeDefined();
        expect(screen.getByText('¥800')).toBeDefined();
        expect(screen.getByText('BeerVolta')).toBeDefined();
        expect(screen.getByText('4.15')).toBeDefined();
    });

    it('should display sale tag and expiry notice when present on item', () => {
        const saleBeers: Beer[] = [{
            ...mockBeers[0],
            is_sale: true,
            sale_tag: '20% OFF SALE',
            expiry_notice: '賞味期限 2026/09'
        }];
        render(<BeerTable beers={saleBeers} loading={false} error={null} />);
        expect(screen.getByText(/20% OFF SALE/)).toBeDefined();
        expect(screen.getByText(/賞味期限 2026\/09/)).toBeDefined();
    });
});

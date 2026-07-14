import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import HomeClient from '../HomeClient';
import type { BeersApiResponse } from '../../types/beer';

const pushMock = vi.fn();
const currentSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useSearchParams: () => currentSearchParams,
    usePathname: () => '/',
}));

describe('HomeClient (Main Page Integration Tests)', () => {
    const initialData: BeersApiResponse = {
        beers: [
            {
                url: 'https://beervolta.example.com/item/1',
                name: 'Test Hazy IPA',
                price: '900円',
                price_value: 900,
                image: 'https://beervolta.example.com/img.jpg',
                stock_status: 'In Stock',
                shop: 'BeerVolta',
                first_seen: '2026-07-01T00:00:00Z',
                last_seen: '2026-07-14T00:00:00Z',
                untappd_url: null,
                is_sale: false,
                sale_tag: null,
                expiry_notice: null,
                brewery_name_en: null,
                brewery_name_jp: null,
                beer_name_en: null,
                beer_name_jp: null,
                product_type: 'beer',
                is_set: false,
                untappd_beer_name: null,
                untappd_brewery_name: null,
                untappd_style: 'IPA - New England / Hazy',
                untappd_abv: 6.5,
                untappd_ibu: 40,
                untappd_rating: 4.0,
                untappd_rating_count: 100,
                untappd_image: null,
                untappd_brewery_url: null,
                untappd_fetched_at: null,
                brewery_location: null,
                brewery_type: null,
                brewery_logo: null,
                brewery_id: null
            }
        ],
        shopCounts: { 'BeerVolta': 10 },
        pagination: {
            page: 1,
            limit: 20,
            total: 1,
            totalPages: 1
        }
    };

    beforeEach(() => {
        vi.clearAllMocks();
        Array.from(currentSearchParams.keys()).forEach(k => currentSearchParams.delete(k));
    });

    it('should render initial data static view without fetching when URL params are empty', async () => {
        const fetchSpy = vi.spyOn(global, 'fetch');
        await act(async () => {
            render(<HomeClient initialData={initialData} availableStyles={[]} availableBreweries={[]} />);
        });

        expect(screen.getByText('Test Hazy IPA')).toBeDefined();
        expect(fetchSpy).not.toHaveBeenCalled();
    });

    it('should update URL when searching beers in the search bar', async () => {
        vi.useFakeTimers();
        await act(async () => {
            render(<HomeClient initialData={initialData} availableStyles={[]} availableBreweries={[]} />);
        });

        const searchInput = screen.getByPlaceholderText('Search beers...');
        act(() => {
            fireEvent.change(searchInput, { target: { value: 'IPA' } });
            vi.advanceTimersByTime(400);
        });

        expect(pushMock).toHaveBeenCalledWith(
            expect.stringContaining('search=IPA'),
            expect.any(Object)
        );
        vi.useRealTimers();
    });

    it('should navigate to /grouped when clicking Grouped view button', async () => {
        await act(async () => {
            render(<HomeClient initialData={initialData} availableStyles={[]} availableBreweries={[]} />);
        });

        const groupedButton = screen.getByText('Grouped');
        act(() => {
            fireEvent.click(groupedButton);
        });

        expect(pushMock).toHaveBeenCalledWith(
            expect.stringContaining('/grouped'),
            expect.any(Object)
        );
    });

    it('should trigger client fetch and display error when fetch to /api/beers returns non-ok response', async () => {
        currentSearchParams.set('page', '2');
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({ error: 'Internal server error' })
        }));

        await act(async () => {
            render(<HomeClient initialData={initialData} availableStyles={[]} availableBreweries={[]} />);
        });

        const errorElement = await screen.findByText('Error: Refresh failed');
        expect(errorElement).toBeDefined();
    });
});

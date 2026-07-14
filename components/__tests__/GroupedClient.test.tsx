import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GroupedClient from '../GroupedClient';
import type { GroupedBeer, GroupedBeersApiResponse } from '../../types/beer';

const pushMock = vi.fn();
let currentSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useSearchParams: () => currentSearchParams,
    usePathname: () => '/grouped',
}));

describe('GroupedClient (Grouped Display Page Integration Tests)', () => {
    const mockGroup: GroupedBeer = {
        group_id: 'g-stout-1',
        beer_name: 'Test Grouped Stout',
        brewery_name: 'Shiga Kogen',
        min_price: '600円',
        max_price: '800円',
        min_price_num: 600,
        max_price_num: 800,
        style: 'Stout',
        abv: '8.0',
        ibu: '60',
        shop_count: 1,
        first_seen: '2026-07-01T00:00:00Z',
        newest_seen: '2026-07-12T00:00:00Z',
        rating: 4.2,
        rating_count: 50,
        untappd_url: 'https://untappd.com/b/shiga-kogen-stout/999',
        beer_image: '',
        product_type: 'beer',
        items: [
            {
                name: 'Test Grouped Stout - BeerVolta',
                url: 'https://beervolta.example.com/stout',
                price: '600円',
                price_value: 600,
                shop: 'BeerVolta',
                stock_status: 'In Stock',
                image: 'https://beervolta.example.com/stout.jpg',
                last_seen: '2026-07-12T00:00:00Z'
            }
        ]
    };

    const initialData: GroupedBeersApiResponse = {
        groups: [mockGroup],
        shopCounts: { 'BeerVolta': 1, 'Chouseiya': 0 },
        pagination: {
            page: 1,
            limit: 20,
            total: 1,
            totalPages: 1
        }
    };

    beforeEach(() => {
        vi.clearAllMocks();
        currentSearchParams = new URLSearchParams();
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: true,
            json: async () => initialData
        }));
    });

    it('should render header, search input, filters, and grouped beer table with initial data', async () => {
        await act(async () => {
            render(
                <GroupedClient
                    initialData={initialData}
                    availableStyles={['Stout', 'IPA']}
                    availableBreweries={[{ name: 'Shiga Kogen', flag: 'JP' }]}
                />
            );
        });

        expect(screen.getByText('Craft Beer Alert Japan')).toBeDefined();
        expect(screen.getByPlaceholderText('Search beers...')).toBeDefined();
        expect(screen.getByText('Test Grouped Stout')).toBeDefined();
        expect(screen.getAllByText('Shiga Kogen').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('BeerVolta')).toBeDefined();
    });

    it('should update URL when searching beers in the search bar', async () => {
        vi.useFakeTimers();
        await act(async () => {
            render(
                <GroupedClient
                    initialData={initialData}
                    availableStyles={['Stout']}
                    availableBreweries={[]}
                />
            );
        });

        const searchInput = screen.getByPlaceholderText('Search beers...');
        act(() => {
            fireEvent.change(searchInput, { target: { value: 'Stout' } });
        });
        act(() => {
            vi.runAllTimers();
        });

        expect(pushMock).toHaveBeenCalledWith(
            expect.stringContaining('search=Stout'),
            expect.any(Object)
        );
        vi.useRealTimers();
    });

    it('should update URL when style filter option is selected from dropdown', async () => {
        await act(async () => {
            render(
                <GroupedClient
                    initialData={initialData}
                    availableStyles={['Stout', 'IPA']}
                    availableBreweries={[]}
                />
            );
        });

        const styleTrigger = screen.getByText('Select Styles');
        act(() => {
            fireEvent.click(styleTrigger);
        });

        const optionIPA = screen.getByText('IPA');
        act(() => {
            fireEvent.click(optionIPA);
        });

        expect(pushMock).toHaveBeenCalledWith(
            expect.stringContaining('style_filter=IPA'),
            expect.any(Object)
        );
    });

    it('should update URL when sort dropdown option is changed', async () => {
        await act(async () => {
            render(
                <GroupedClient
                    initialData={initialData}
                    availableStyles={[]}
                    availableBreweries={[]}
                />
            );
        });

        const sortSelects = screen.getAllByRole('combobox');
        const sortSelect = sortSelects.find(s => (s as HTMLSelectElement).value === 'newest') || sortSelects[0];

        act(() => {
            fireEvent.change(sortSelect, { target: { value: 'price_asc' } });
        });

        expect(pushMock).toHaveBeenCalledWith(
            expect.stringContaining('sort=price_asc'),
            expect.any(Object)
        );
    });

    it('should reset filters when clicking the header title', async () => {
        currentSearchParams.set('search', 'old query');
        await act(async () => {
            render(
                <GroupedClient
                    initialData={initialData}
                    availableStyles={[]}
                    availableBreweries={[]}
                />
            );
        });

        const headerLink = screen.getByText('Craft Beer Alert Japan');
        act(() => {
            fireEvent.click(headerLink);
        });

        expect(pushMock).toHaveBeenCalled();
        const lastCall = pushMock.mock.calls[pushMock.mock.calls.length - 1][0];
        expect(lastCall).not.toContain('search=old query');
    });

    it('should display "Error: Refresh failed" when client fetch to /api/grouped-beers fails with 500 status', async () => {
        currentSearchParams.set('search', 'failing-query');
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            json: async () => ({ error: 'Internal server error' })
        }));

        await act(async () => {
            render(
                <GroupedClient
                    initialData={initialData}
                    availableStyles={[]}
                    availableBreweries={[]}
                />
            );
        });

        // Because searchParams has parameters, GroupedClient triggers fetchData() via useEffect on mount
        const errorElement = await screen.findByText('Error: Refresh failed');
        expect(errorElement).toBeDefined();
    });
});

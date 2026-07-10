import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import GroupedBeerTable from '../GroupedBeerTable';
import type { GroupedBeer } from '../../types/beer';

describe('GroupedBeerTable stockFilter behavior', () => {
    const mockGroups: GroupedBeer[] = [
        {
            group_id: 'group-1',
            beer_name: 'Test IPA',
            brewery_name: 'Test Brewery',
            min_price: '1000円',
            max_price: '1200円',
            min_price_num: 1000,
            max_price_num: 1200,
            style: 'IPA',
            abv: '6.5',
            ibu: '50',
            shop_count: 2,
            first_seen: '2026-07-01T00:00:00Z',
            newest_seen: '2026-07-10T00:00:00Z',
            rating: 4.0,
            rating_count: 100,
            untappd_url: 'https://untappd.com/b/test-ipa/123',
            beer_image: '',
            product_type: 'beer',
            items: [
                {
                    name: 'Test IPA - Shop A',
                    url: 'https://shopa.example.com/item/1',
                    price: '1000円',
                    price_value: 1000,
                    shop: 'Shop A',
                    stock_status: 'In Stock',
                    image: 'https://shopa.example.com/img.jpg',
                    last_seen: '2026-07-10T00:00:00Z'
                },
                {
                    name: 'Test IPA - Shop B',
                    url: 'https://shopb.example.com/item/2',
                    price: '1200円',
                    price_value: 1200,
                    shop: 'Shop B',
                    stock_status: 'Sold Out',
                    image: 'https://shopb.example.com/img.jpg',
                    last_seen: '2026-07-10T00:00:00Z'
                }
            ]
        }
    ];

    it('should filter out Sold Out shop items when stockFilter is in_stock', () => {
        render(<GroupedBeerTable groups={mockGroups} loading={false} error={null} stockFilter="in_stock" />);
        expect(screen.getByText('Shop A')).toBeDefined();
        expect(screen.queryByText('Shop B')).toBeNull();
    });

    it('should show both In Stock and Sold Out shop items when stockFilter is all', () => {
        render(<GroupedBeerTable groups={mockGroups} loading={false} error={null} stockFilter="all" />);
        expect(screen.getByText('Shop A')).toBeDefined();
        expect(screen.getByText('Shop B')).toBeDefined();
    });

    it('should only show Sold Out shop items when stockFilter is sold_out', () => {
        render(<GroupedBeerTable groups={mockGroups} loading={false} error={null} stockFilter="sold_out" />);
        expect(screen.queryByText('Shop A')).toBeNull();
        expect(screen.getByText('Shop B')).toBeDefined();
    });

    it('should not render a group row if all items are filtered out by stockFilter', () => {
        const soldOutOnlyGroups: GroupedBeer[] = [
            {
                ...mockGroups[0],
                items: [mockGroups[0].items[1]] // only Shop B (Sold Out)
            }
        ];
        const { container } = render(<GroupedBeerTable groups={soldOutOnlyGroups} loading={false} error={null} stockFilter="in_stock" />);
        expect(screen.queryByText('Test IPA')).toBeNull();
    });
});

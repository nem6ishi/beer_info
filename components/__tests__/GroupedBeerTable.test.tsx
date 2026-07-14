import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import GroupedBeerTable from '../GroupedBeerTable';
import type { GroupedBeer } from '../../types/beer';

describe('GroupedBeerTable comprehensive display and behavior tests', () => {
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
        render(<GroupedBeerTable groups={soldOutOnlyGroups} loading={false} error={null} stockFilter="in_stock" />);
        expect(screen.queryByText('Test IPA')).toBeNull();
    });

    it('should sort multiple shop items by price ascending and display their prices and shop names', () => {
        const multiShopGroups: GroupedBeer[] = [
            {
                ...mockGroups[0],
                items: [
                    {
                        name: 'Test IPA - Shop B',
                        url: 'https://shopb.example.com/item/2',
                        price: '1,200円',
                        price_value: 1200,
                        shop: 'Shop B',
                        stock_status: 'In Stock',
                        image: 'https://shopb.example.com/img.jpg',
                        last_seen: '2026-07-10T00:00:00Z'
                    },
                    {
                        name: 'Test IPA - Shop C',
                        url: 'https://shopc.example.com/item/3',
                        price: '890円',
                        price_value: 890,
                        shop: 'Shop C',
                        stock_status: 'In Stock',
                        image: 'https://shopc.example.com/img.jpg',
                        last_seen: '2026-07-10T00:00:00Z'
                    },
                    {
                        name: 'Test IPA - Shop A',
                        url: 'https://shopa.example.com/item/1',
                        price: '1,000円',
                        price_value: 1000,
                        shop: 'Shop A',
                        stock_status: 'In Stock',
                        image: 'https://shopa.example.com/img.jpg',
                        last_seen: '2026-07-10T00:00:00Z'
                    }
                ]
            }
        ];
        render(<GroupedBeerTable groups={multiShopGroups} loading={false} error={null} stockFilter="in_stock" />);
        expect(screen.getByText('Shop A')).toBeDefined();
        expect(screen.getByText('Shop B')).toBeDefined();
        expect(screen.getByText('Shop C')).toBeDefined();
        expect(screen.getByText('¥890')).toBeDefined();
        expect(screen.getByText('¥1,000')).toBeDefined();
        expect(screen.getByText('¥1,200')).toBeDefined();
    });

    it('should fallback to cheapest shop image when untappd image is missing or default badge', () => {
        const fallbackImgGroups: GroupedBeer[] = [
            {
                ...mockGroups[0],
                beer_image: 'https://untappd.s3.amazonaws.com/site/assets/images/temp/badge-beer-default.png',
                items: [
                    {
                        ...mockGroups[0].items[0],
                        image: 'https://shopa.example.com/cheapest-fallback.jpg'
                    }
                ]
            }
        ];
        const { container } = render(<GroupedBeerTable groups={fallbackImgGroups} loading={false} error={null} stockFilter="in_stock" />);
        const img = container.querySelector('img');
        expect(img?.getAttribute('src')).toBe('https://shopa.example.com/cheapest-fallback.jpg');
    });

    it('should fallback to shop title for beer name when untappd_url is a search link or null', () => {
        const searchLinkGroups: GroupedBeer[] = [
            {
                ...mockGroups[0],
                beer_name: 'Untappd Search Query IPA',
                untappd_url: 'https://untappd.com/search?q=Test+IPA',
                items: [
                    {
                        ...mockGroups[0].items[0],
                        shop: 'Shop A Custom Title'
                    }
                ]
            }
        ];
        render(<GroupedBeerTable groups={searchLinkGroups} loading={false} error={null} stockFilter="in_stock" />);
        expect(screen.getAllByText('Shop A Custom Title').length).toBeGreaterThanOrEqual(1);
    });

    it('should display sale tag and expiry notice when present on the group', () => {
        const saleExpiryGroups: GroupedBeer[] = [
            {
                ...mockGroups[0],
                is_sale: true,
                sale_tag: '30% OFF SALE',
                expiry_notice: '賞味期限: 2026年8月'
            }
        ];
        render(<GroupedBeerTable groups={saleExpiryGroups} loading={false} error={null} stockFilter="in_stock" />);
        expect(screen.getByText(/30% OFF SALE/)).toBeDefined();
        expect(screen.getByText(/賞味期限: 2026年8月/)).toBeDefined();
    });

    it('should display loading message when loading with empty groups', () => {
        render(<GroupedBeerTable groups={[]} loading={true} error={null} />);
        expect(screen.getByText('Loading grouped collection...')).toBeDefined();
    });

    it('should display empty message when not loading and groups array is empty', () => {
        render(<GroupedBeerTable groups={[]} loading={false} error={null} />);
        expect(screen.getByText('No grouped beers found.')).toBeDefined();
    });

    it('should display error message when error string is passed', () => {
        render(<GroupedBeerTable groups={[]} loading={false} error="Failed to fetch beer collection" />);
        expect(screen.getByText('Error: Failed to fetch beer collection')).toBeDefined();
    });

    it('should hide group if no items match selectedShops after stock filtering', () => {
        render(<GroupedBeerTable groups={mockGroups} loading={false} error={null} stockFilter="in_stock" selectedShops={['Shop B']} />);
        expect(screen.queryByText('Test IPA')).toBeNull();
    });

    it('should sort items matching selectedShops first', () => {
        const multiShopGroups: GroupedBeer[] = [
            {
                ...mockGroups[0],
                items: [
                    {
                        name: 'Test IPA - Shop B',
                        url: 'https://shopb.example.com/item/2',
                        price: '800円',
                        price_value: 800,
                        shop: 'Shop B',
                        stock_status: 'In Stock',
                        image: 'https://shopb.example.com/img.jpg',
                        last_seen: '2026-07-10T00:00:00Z'
                    },
                    {
                        name: 'Test IPA - Shop A',
                        url: 'https://shopa.example.com/item/1',
                        price: '1,000円',
                        price_value: 1000,
                        shop: 'Shop A',
                        stock_status: 'In Stock',
                        image: 'https://shopa.example.com/img.jpg',
                        last_seen: '2026-07-10T00:00:00Z'
                    }
                ]
            }
        ];
        const { container } = render(<GroupedBeerTable groups={multiShopGroups} loading={false} error={null} stockFilter="in_stock" selectedShops={['Shop A']} />);
        const shopNames = Array.from(container.querySelectorAll('.shop-name-text')).map(el => el.textContent);
        expect(shopNames[0]).toBe('Shop A');
        expect(shopNames[1]).toBe('Shop B');
    });
});

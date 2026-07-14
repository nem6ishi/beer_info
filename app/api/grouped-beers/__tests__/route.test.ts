import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GET } from '../route';
import { getGroupedBeers } from '../../../../lib/groupedBeers';

vi.mock('../../../../lib/groupedBeers', () => ({
    getGroupedBeers: vi.fn(),
}));

describe('GET /api/grouped-beers (API Route Handler Tests)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should return 200 and formatted pagination response when getGroupedBeers succeeds', async () => {
        const mockGroups = [{ group_id: '1', beer_name: 'Test Beer' }];
        const mockShopCounts = { 'BeerVolta': 5 };
        
        vi.mocked(getGroupedBeers).mockResolvedValueOnce({
            groupsData: mockGroups,
            shopCounts: mockShopCounts,
            totalCount: 1
        });

        const req = new Request('http://localhost:3000/api/grouped-beers?page=1&limit=20&sort=newest');
        const res = await GET(req);

        expect(res.status).toBe(200);
        const json = await res.json();
        expect(json).toEqual({
            groups: mockGroups,
            shopCounts: mockShopCounts,
            pagination: {
                page: 1,
                limit: 20,
                total: 1,
                totalPages: 1
            }
        });
        expect(res.headers.get('Cache-Control')).toContain('public, s-maxage=60');
    });

    it('should correctly parse and forward all search parameters to getGroupedBeers', async () => {
        vi.mocked(getGroupedBeers).mockResolvedValueOnce({
            groupsData: [],
            shopCounts: {},
            totalCount: 0
        });

        const req = new Request('http://localhost:3000/api/grouped-beers?search=Stout&sort=price_asc&page=2&limit=50&shop=BeerVolta&min_abv=6.0&style_filter=Stout&stock_filter=in_stock&only_sale=1');
        await GET(req);

        expect(getGroupedBeers).toHaveBeenCalledWith({
            search: 'Stout',
            sort: 'price_asc',
            page: 2,
            limit: 50,
            shop: 'BeerVolta',
            min_abv: '6.0',
            max_abv: null,
            min_ibu: null,
            max_ibu: null,
            min_rating: null,
            style_filter: 'Stout',
            stock_filter: 'in_stock',
            product_type: null,
            brewery_filter: null,
            days: null,
            only_sale: '1'
        });
    });

    it('should catch database errors (like 22P02 invalid json syntax) and return 500 status to prevent unhandled crashes', async () => {
        const dbSyntaxError = {
            code: '22P02',
            details: 'Expected string or "}", but found "[".',
            hint: null,
            message: 'invalid input syntax for type json'
        };

        vi.mocked(getGroupedBeers).mockRejectedValueOnce(dbSyntaxError);

        const req = new Request('http://localhost:3000/api/grouped-beers?stock_filter=in_stock');
        const res = await GET(req);

        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json).toEqual({ error: 'Internal server error' });
    });
});

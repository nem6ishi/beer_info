import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GET } from '../route';
import { supabase } from '../../../../lib/supabase';

const {
    rangeMock, eqMock, gteMock, lteMock, orMock, inMock, orderMock, notMock, rpcMock, queryBuilder, selectMock
} = vi.hoisted(() => {
    const rangeMock = vi.fn().mockResolvedValue({ data: [], count: 0, error: null });
    const eqMock = vi.fn();
    const gteMock = vi.fn();
    const lteMock = vi.fn();
    const orMock = vi.fn();
    const inMock = vi.fn();
    const orderMock = vi.fn();
    const notMock = vi.fn();
    const rpcMock = vi.fn().mockResolvedValue({ data: [] });

    const queryBuilder: any = {
        range: (...args: any[]) => rangeMock(...args),
        eq: (...args: any[]) => { eqMock(...args); return queryBuilder; },
        gte: (...args: any[]) => { gteMock(...args); return queryBuilder; },
        lte: (...args: any[]) => { lteMock(...args); return queryBuilder; },
        or: (...args: any[]) => { orMock(...args); return queryBuilder; },
        in: (...args: any[]) => { inMock(...args); return queryBuilder; },
        order: (...args: any[]) => { orderMock(...args); return queryBuilder; },
        not: (...args: any[]) => { notMock(...args); return queryBuilder; },
    };
    const selectMock = vi.fn().mockReturnValue(queryBuilder);
    queryBuilder.select = (...args: any[]) => { selectMock(...args); return queryBuilder; };

    return { rangeMock, eqMock, gteMock, lteMock, orMock, inMock, orderMock, notMock, rpcMock, queryBuilder, selectMock };
});

vi.mock('../../../../lib/supabase', () => ({
    supabase: {
        from: vi.fn().mockReturnValue(queryBuilder),
        rpc: (...args: any[]) => rpcMock(...args)
    }
}));

describe('GET /api/beers (Individual Display API Route Tests)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        selectMock.mockReturnValue(queryBuilder);
        rangeMock.mockResolvedValue({ data: [], count: 0, error: null });
        eqMock.mockReturnThis();
        gteMock.mockReturnThis();
        lteMock.mockReturnThis();
        orMock.mockReturnThis();
        inMock.mockReturnThis();
        orderMock.mockReturnThis();
        notMock.mockReturnThis();
        rpcMock.mockResolvedValue({ data: [] });
    });

    it('should return 200 with formatted beers, shopCounts, and pagination on success', async () => {
        const mockBeers = [{ url: 'http://shop.com/1', name: 'Test IPA' }];
        const mockShopCounts = [{ shop: 'BeerVolta', shop_count: 10 }];
        
        rangeMock.mockResolvedValueOnce({ data: mockBeers, count: 1, error: null });
        rpcMock.mockResolvedValueOnce({ data: mockShopCounts, error: null });

        const req = new Request('http://localhost:3000/api/beers?page=1&limit=20');
        const res = await GET(req);

        expect(res.status).toBe(200);
        const json = await res.json();
        expect(json).toEqual({
            beers: mockBeers,
            shopCounts: { 'BeerVolta': 10 },
            pagination: {
                page: 1,
                limit: 20,
                total: 1,
                totalPages: 1
            }
        });
        expect(res.headers.get('Cache-Control')).toContain('public, s-maxage=60');
    });

    it('should query beer_info_view with exact filters (in_stock default)', async () => {
        const req = new Request('http://localhost:3000/api/beers?page=1&limit=20');
        await GET(req);

        expect(supabase.from).toHaveBeenCalledWith('beer_info_view');
        expect(eqMock).toHaveBeenCalledWith('stock_status', 'In Stock');
        expect(rpcMock).toHaveBeenCalledWith('get_filtered_shop_counts', expect.objectContaining({
            p_stock_filter: 'in_stock'
        }));
    });

    it('should return 500 when Supabase query returns an error', async () => {
        rangeMock.mockResolvedValueOnce({ data: null, count: null, error: { message: 'Database query failed' } });

        const req = new Request('http://localhost:3000/api/beers');
        const res = await GET(req);

        expect(res.status).toBe(500);
        const json = await res.json();
        expect(json).toEqual({ error: 'Internal server error' });
    });
});

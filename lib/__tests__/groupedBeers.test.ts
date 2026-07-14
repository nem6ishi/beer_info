import { describe, it, expect, vi, beforeEach } from 'vitest';

const containsMock = vi.fn().mockReturnThis();
const notMock = vi.fn().mockReturnThis();
const rangeMock = vi.fn().mockResolvedValue({ data: [], count: 0, error: null });
const orMock = vi.fn().mockReturnThis();
const gteMock = vi.fn().mockReturnThis();
const lteMock = vi.fn().mockReturnThis();
const eqMock = vi.fn().mockReturnThis();
const inMock = vi.fn().mockReturnThis();
const orderMock = vi.fn().mockReturnThis();
const selectMock = vi.fn().mockReturnThis();

const rpcMock = vi.fn().mockResolvedValue({ data: [] });
const fromMock = vi.fn().mockReturnValue({
    select: selectMock,
    contains: containsMock,
    not: notMock,
    range: rangeMock,
    or: orMock,
    gte: gteMock,
    lte: lteMock,
    eq: eqMock,
    in: inMock,
    order: orderMock
});

vi.mock('../supabase', () => ({
    supabase: {
        from: (...args: any[]) => fromMock(...args),
        rpc: (...args: any[]) => rpcMock(...args)
    }
}));

import { getGroupedBeers } from '../groupedBeers';

describe('getGroupedBeers filter behavior', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        selectMock.mockReturnThis();
        containsMock.mockReturnThis();
        notMock.mockReturnThis();
        rangeMock.mockResolvedValue({ data: [], count: 0, error: null });
        orMock.mockReturnThis();
        gteMock.mockReturnThis();
        lteMock.mockReturnThis();
        eqMock.mockReturnThis();
        inMock.mockReturnThis();
        orderMock.mockReturnThis();
        fromMock.mockReturnValue({
            select: selectMock,
            contains: containsMock,
            not: notMock,
            range: rangeMock,
            or: orMock,
            gte: gteMock,
            lte: lteMock,
            eq: eqMock,
            in: inMock,
            order: orderMock
        });
        rpcMock.mockResolvedValue({ data: [] });
    });

    it('should default to in_stock filtering when stock_filter is null/omitted', async () => {
        await getGroupedBeers({
            page: 1,
            limit: 20,
            sort: 'newest',
            search: '',
            shop: '',
            min_abv: null,
            max_abv: null,
            min_ibu: null,
            max_ibu: null,
            min_rating: null,
            style_filter: null,
            stock_filter: null,
            product_type: null,
            brewery_filter: null
        });

        expect(containsMock).toHaveBeenCalledWith('items', '[{"stock_status":"In Stock"}]');
        expect(rpcMock).toHaveBeenCalledWith('get_filtered_shop_counts', expect.objectContaining({
            p_stock_filter: 'in_stock'
        }));
    });

    it('should filter by sold_out when stock_filter is sold_out', async () => {
        await getGroupedBeers({
            page: 1,
            limit: 20,
            sort: 'newest',
            search: '',
            shop: '',
            min_abv: null,
            max_abv: null,
            min_ibu: null,
            max_ibu: null,
            min_rating: null,
            style_filter: null,
            stock_filter: 'sold_out',
            product_type: null,
            brewery_filter: null
        });

        expect(notMock).toHaveBeenCalledWith('items', 'cs', '[{"stock_status":"In Stock"}]');
        expect(rpcMock).toHaveBeenCalledWith('get_filtered_shop_counts', expect.objectContaining({
            p_stock_filter: 'sold_out'
        }));
    });

    it('should not apply stock filter query when stock_filter is all', async () => {
        await getGroupedBeers({
            page: 1,
            limit: 20,
            sort: 'newest',
            search: '',
            shop: '',
            min_abv: null,
            max_abv: null,
            min_ibu: null,
            max_ibu: null,
            min_rating: null,
            style_filter: null,
            stock_filter: 'all',
            product_type: null,
            brewery_filter: null
        });

        expect(containsMock).not.toHaveBeenCalled();
        expect(notMock).not.toHaveBeenCalled();
        expect(rpcMock).toHaveBeenCalledWith('get_filtered_shop_counts', expect.objectContaining({
            p_stock_filter: null
        }));
    });

    it('should throw database execution errors when dataRes.error occurs (e.g. 22P02 invalid json syntax)', async () => {
        const syntaxError = {
            code: '22P02',
            message: 'invalid input syntax for type json',
            details: 'Expected string or "}", but found "["'
        };
        rangeMock.mockResolvedValueOnce({ data: null, count: null, error: syntaxError });

        await expect(getGroupedBeers({
            page: 1, limit: 20, sort: 'newest', search: '', shop: '',
            min_abv: null, max_abv: null, min_ibu: null, max_ibu: null, min_rating: null,
            style_filter: null, stock_filter: 'in_stock', product_type: null, brewery_filter: null
        })).rejects.toEqual(syntaxError);
    });

    it('should combine shop and in_stock filter using item-level shop+stock_status matching', async () => {
        await getGroupedBeers({
            page: 1,
            limit: 20,
            sort: 'newest',
            search: '',
            shop: 'arome',
            min_abv: null,
            max_abv: null,
            min_ibu: null,
            max_ibu: null,
            min_rating: null,
            style_filter: null,
            stock_filter: 'in_stock',
            product_type: null,
            brewery_filter: null
        });

        expect(orMock).toHaveBeenCalledWith('items.cs.[{"shop":"arome","stock_status":"In Stock"}]');
    });

    it('should combine shop and sold_out filter using item-level matching', async () => {
        await getGroupedBeers({
            page: 1,
            limit: 20,
            sort: 'newest',
            search: '',
            shop: 'arome',
            min_abv: null,
            max_abv: null,
            min_ibu: null,
            max_ibu: null,
            min_rating: null,
            style_filter: null,
            stock_filter: 'sold_out',
            product_type: null,
            brewery_filter: null
        });

        expect(orMock).toHaveBeenCalledWith('items.cs.[{"shop":"arome"}]');
        expect(notMock).toHaveBeenCalledWith('items', 'cs', '[{"shop":"arome","stock_status":"In Stock"}]');
    });
});

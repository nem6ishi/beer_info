import { describe, it, expect, vi, beforeEach } from 'vitest';

const notMock = vi.fn().mockReturnThis();
const neqMock = vi.fn().mockReturnThis();
const selectMock = vi.fn().mockReturnThis();
const rangeMock = vi.fn();
const singleMock = vi.fn();
const rpcMock = vi.fn().mockReturnValue({ single: singleMock });

const fromMock = vi.fn().mockReturnValue({
    select: selectMock,
    not: notMock,
    neq: neqMock,
    range: rangeMock
});

vi.mock('../supabase', () => ({
    supabase: {
        from: (...args: any[]) => fromMock(...args),
        rpc: (...args: any[]) => rpcMock(...args)
    }
}));

import { getFlag, fetchAvailableBreweries } from '../breweries';

describe('lib/breweries', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        selectMock.mockReturnThis();
        notMock.mockReturnThis();
        neqMock.mockReturnThis();
        fromMock.mockReturnValue({
            select: selectMock,
            not: notMock,
            neq: neqMock,
            range: rangeMock
        });
        rpcMock.mockReturnValue({ single: singleMock });
    });

    describe('getFlag', () => {
        it('returns correct flag for known locations', () => {
            expect(getFlag('Tokyo, Japan')).toBe('🇯🇵');
            expect(getFlag('San Diego, CA United States')).toBe('🇺🇸');
            expect(getFlag('London, United Kingdom')).toBe('🇬🇧');
            expect(getFlag('Munich, Germany')).toBe('🇩🇪');
            expect(getFlag(null)).toBe('🏳️');
            expect(getFlag('Unknown Country')).toBe('🏳️');
        });
    });

    describe('fetchAvailableBreweries', () => {
        it('uses RPC when valid breweries array with name property is returned', async () => {
            singleMock.mockResolvedValue({
                data: {
                    breweries: [
                        { name: 'Brewery B', location: 'USA', searchStr: 'Brewery B' },
                        { name: 'Brewery A', location: 'Japan', searchStr: 'Brewery A' }
                    ]
                },
                error: null
            });

            const result = await fetchAvailableBreweries(true);

            expect(result).toHaveLength(2);
            expect(result[0].name).toBe('Brewery A');
            expect(result[0].flag).toBe('🇯🇵');
            expect(result[1].name).toBe('Brewery B');
            expect(result[1].flag).toBe('🇺🇸');
        });

        it('falls back to paginated beer_info_view fetch when RPC returns old structure without name', async () => {
            // Simulate old RPC returning { name_en, name_jp }
            singleMock.mockResolvedValue({
                data: {
                    breweries: [
                        { name_en: 'Old Brewery', name_jp: 'オールド' }
                    ]
                },
                error: null
            });

            // Simulate 2 pages of data (e.g. 1000 items in page 1, 1 item in page 2)
            const page1Data = Array.from({ length: 1000 }, (_, i) => ({
                untappd_brewery_name: `Brewery ${i}`,
                brewery_location: 'Japan',
                brewery_name_jp: `ブルワリー${i}`,
                brewery_name_en: `Brewery ${i}`
            }));
            const page2Data = [
                {
                    untappd_brewery_name: 'Newest Brewery',
                    brewery_location: 'United States',
                    brewery_name_jp: '新着ブルワリー',
                    brewery_name_en: 'Newest Brewery'
                }
            ];

            rangeMock
                .mockResolvedValueOnce({ data: page1Data, error: null })
                .mockResolvedValueOnce({ data: page2Data, error: null });

            const result = await fetchAvailableBreweries(true);

            expect(fromMock).toHaveBeenCalledWith('beer_info_view');
            expect(rangeMock).toHaveBeenCalledTimes(2);
            expect(rangeMock).toHaveBeenNthCalledWith(1, 0, 999);
            expect(rangeMock).toHaveBeenNthCalledWith(2, 1000, 1999);

            const newest = result.find(b => b.name === 'Newest Brewery');
            expect(newest).toBeDefined();
            expect(newest?.flag).toBe('🇺🇸');
            expect(newest?.searchStr).toContain('新着ブルワリー');
        });
    });
});

import { renderHook, act } from '@testing-library/react';
import { useBeerFilters } from '../useBeerFilters';
import { vi, describe, it, expect, beforeEach } from 'vitest';

const pushMock = vi.fn();
let currentSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useSearchParams: () => currentSearchParams,
    usePathname: () => '/beers',
}));

describe('useBeerFilters', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        currentSearchParams = new URLSearchParams();
    });

    it('should initialize with default values', () => {
        const { result } = renderHook(() => useBeerFilters());
        
        expect(result.current.searchInput).toBe('');
        expect(result.current.isFilterOpen).toBe(false);
        expect(result.current.tempFilters.stock_filter).toBe('in_stock');
    });

    it('should handle multi-select change and update state', () => {
        const { result } = renderHook(() => useBeerFilters());

        act(() => {
            result.current.handleMultiSelectChange('style_filter', ['IPA', 'Stout']);
        });

        expect(result.current.tempFilters.style_filter).toBe('IPA,Stout');
        expect(pushMock).toHaveBeenCalled();
        expect(pushMock.mock.calls[0][0]).toContain('style_filter=IPA%2CStout');
    });

    it('should sync filters from params', () => {
        currentSearchParams.set('search', 'Test Beer');
        currentSearchParams.set('min_abv', '5');
        
        const { result } = renderHook(() => useBeerFilters());

        act(() => {
            result.current.syncFiltersFromParams();
        });

        expect(result.current.searchInput).toBe('Test Beer');
        expect(result.current.tempFilters.min_abv).toBe('5');
    });

    it('should handle stock_filter changes and remove param when set to in_stock default', () => {
        vi.useFakeTimers();
        const { result } = renderHook(() => useBeerFilters());

        act(() => {
            result.current.handleFilterChange('stock_filter', 'sold_out');
        });
        act(() => {
            vi.runAllTimers();
        });
        expect(pushMock).toHaveBeenCalledWith(expect.stringContaining('stock_filter=sold_out'), { scroll: false });

        act(() => {
            result.current.handleFilterChange('stock_filter', 'in_stock');
        });
        act(() => {
            vi.runAllTimers();
        });
        // Since in_stock is default, it should delete stock_filter from URL
        const lastCall = pushMock.mock.calls[pushMock.mock.calls.length - 1][0];
        expect(lastCall).not.toContain('stock_filter=in_stock');
        vi.useRealTimers();
    });
});

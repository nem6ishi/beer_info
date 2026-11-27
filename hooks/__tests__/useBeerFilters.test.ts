import { renderHook, act } from '@testing-library/react';
import { useBeerFilters } from '../useBeerFilters';
import { vi, describe, it, expect, beforeEach } from 'vitest';

const pushMock = vi.fn();
let currentSearchParams = new URLSearchParams();
let pushStateSpy: any;

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
        pushStateSpy = vi.spyOn(window.history, 'pushState').mockImplementation(() => {});
    });

    afterEach(() => {
        vi.useRealTimers();
        pushStateSpy?.mockRestore?.();
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

        expect(result.current.tempFilters.style_filter).toBe('IPA|Stout');
        expect(pushStateSpy).toHaveBeenCalledWith(null, '', expect.stringContaining('style_filter=IPA%7CStout'));
    });

    it('should sync filters from params including product_type', () => {
        currentSearchParams.set('search', 'Test Beer');
        currentSearchParams.set('min_abv', '5');
        currentSearchParams.set('product_type', 'set');
        
        const { result } = renderHook(() => useBeerFilters());

        act(() => {
            result.current.syncFiltersFromParams();
        });

        expect(result.current.searchInput).toBe('Test Beer');
        expect(result.current.tempFilters.min_abv).toBe('5');
        expect(result.current.tempFilters.product_type).toBe('set');
    });

    it('should preserve both rapid immediate filter clicks and rapid numeric inputs without overwriting', () => {
        vi.useFakeTimers();
        const { result } = renderHook(() => useBeerFilters());

        act(() => {
            result.current.handleFilterChange('days', '1');
            result.current.handleFilterChange('only_sale', '1');
        });

        const lastImmediateUrl = pushStateSpy.mock.calls[pushStateSpy.mock.calls.length - 1][2];
        expect(lastImmediateUrl).toContain('days=1');
        expect(lastImmediateUrl).toContain('only_sale=1');

        act(() => {
            result.current.handleFilterChange('min_abv', '8');
            result.current.handleFilterChange('max_abv', '10');
        });
        act(() => {
            vi.runAllTimers();
        });

        const lastRangeUrl = pushStateSpy.mock.calls[pushStateSpy.mock.calls.length - 1][2];
        expect(lastRangeUrl).toContain('min_abv=8');
        expect(lastRangeUrl).toContain('max_abv=10');
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
        expect(pushStateSpy).toHaveBeenCalledWith(null, '', expect.stringContaining('stock_filter=sold_out'));

        act(() => {
            result.current.handleFilterChange('stock_filter', 'in_stock');
        });
        act(() => {
            vi.runAllTimers();
        });
        // Since in_stock is default, it should delete stock_filter from URL
        const lastCall = pushStateSpy.mock.calls[pushStateSpy.mock.calls.length - 1][2];
        expect(lastCall).not.toContain('stock_filter=in_stock');
    });

    it('should use router.push when navigating to a different pathname', () => {
        const { result } = renderHook(() => useBeerFilters());

        act(() => {
            result.current.updateURL({}, '/grouped');
        });

        expect(pushMock).toHaveBeenCalledWith('/grouped', { scroll: false });
    });
});

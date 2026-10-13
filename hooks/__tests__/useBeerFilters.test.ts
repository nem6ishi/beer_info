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

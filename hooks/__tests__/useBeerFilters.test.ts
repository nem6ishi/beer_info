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
});

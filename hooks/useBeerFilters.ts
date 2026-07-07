import { useState, useRef, useTransition, useCallback } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import type { FilterState } from '../types/beer';

export function useBeerFilters() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const pathname = usePathname();
    const [isPending, startTransition] = useTransition();

    const searchParamStr = searchParams.get('search') || '';
    const [searchInput, setSearchInput] = useState(searchParamStr);
    const [isFilterOpen, setIsFilterOpen] = useState(false);
    
    const [tempFilters, setTempFilters] = useState<FilterState>({
        min_abv: searchParams.get('min_abv') || '', 
        max_abv: searchParams.get('max_abv') || '', 
        min_ibu: searchParams.get('min_ibu') || '', 
        max_ibu: searchParams.get('max_ibu') || '', 
        min_rating: searchParams.get('min_rating') || '',
        stock_filter: searchParams.get('stock_filter') || 'in_stock', 
        untappd_status: searchParams.get('untappd_status') || '', 
        shop: searchParams.get('shop') || '',
        brewery_filter: searchParams.get('brewery_filter') || '', 
        style_filter: searchParams.get('style_filter') || '', 
        set_mode: searchParams.get('set_mode') || '',
        days: searchParams.get('days') || '',
        debug: searchParams.get('debug') || '',
        only_sale: searchParams.get('only_sale') || ''
    });

    const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const filterTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const updateURL = useCallback((newParams: Record<string, string>, targetPath = pathname) => {
        const params = new URLSearchParams(searchParams.toString());
        
        Object.entries(newParams).forEach(([key, value]) => {
            if (value === '') {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        });

        if (params.get('page') === '1') params.delete('page');
        if (params.get('limit') === '20') params.delete('limit');
        if (params.get('sort') === 'newest') params.delete('sort');
        if (!params.get('search')) params.delete('search');
        if (!params.get('shop')) params.delete('shop');
        if (params.get('stock_filter') === 'in_stock') params.delete('stock_filter');

        const searchStr = params.toString();
        const queryStr = searchStr ? `?${searchStr}` : '';
        startTransition(() => {
            router.push(`${targetPath}${queryStr}`, { scroll: false });
        });
    }, [pathname, router, searchParams]);

    const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        setSearchInput(val);
        if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
        searchTimeoutRef.current = setTimeout(() => updateURL({ search: val, page: '1' }), 300);
    }, [updateURL]);

    const handleFilterChange = useCallback((key: string, value: string) => {
        setTempFilters(prev => ({ ...prev, [key]: value }));
        if (filterTimeoutRef.current) clearTimeout(filterTimeoutRef.current);
        filterTimeoutRef.current = setTimeout(() => {
            updateURL({ [key]: value, page: '1' });
        }, 300);
    }, [updateURL]);
    
    const handleMultiSelectChange = useCallback((key: string, value: string[]) => {
        setTempFilters(prev => ({ ...prev, [key]: value.join(',') }));
        updateURL({ [key]: value.join(','), page: '1' });
    }, [updateURL]);

    const resetFilters = useCallback(() => {
        startTransition(() => {
            router.push(pathname, { scroll: false });
        });
    }, [pathname, router]);

    const syncFiltersFromParams = useCallback(() => {
        setSearchInput(searchParams.get('search') || '');
        setTempFilters({
            min_abv: searchParams.get('min_abv') || '',
            max_abv: searchParams.get('max_abv') || '',
            min_ibu: searchParams.get('min_ibu') || '',
            max_ibu: searchParams.get('max_ibu') || '',
            min_rating: searchParams.get('min_rating') || '',
            stock_filter: searchParams.get('stock_filter') || 'in_stock',
            untappd_status: searchParams.get('untappd_status') || '',
            shop: searchParams.get('shop') || '',
            brewery_filter: searchParams.get('brewery_filter') || '',
            style_filter: searchParams.get('style_filter') || '',
            set_mode: searchParams.get('set_mode') || '',
            days: searchParams.get('days') || '',
            debug: searchParams.get('debug') || '',
            only_sale: searchParams.get('only_sale') || ''
        });
    }, [searchParams]);

    return {
        searchInput,
        isFilterOpen,
        setIsFilterOpen,
        tempFilters,
        isPending,
        updateURL,
        handleSearchChange,
        handleFilterChange,
        handleMultiSelectChange,
        resetFilters,
        syncFiltersFromParams,
        searchParams,
        pathname
    };
}

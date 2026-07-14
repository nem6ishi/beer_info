import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import BeerFilters from '../BeerFilters';

describe('BeerFilters Unit Tests', () => {
    const mockTempFilters = {
        min_abv: '',
        max_abv: '',
        min_ibu: '',
        max_ibu: '',
        min_rating: '',
        stock_filter: 'in_stock',
        product_type: '',
        untappd_status: '',
        days: '',
        only_sale: ''
    };

    const defaultProps = {
        shop: '',
        shopCounts: { 'BeerVolta': 10 },
        brewery_filter: '',
        style_filter: '',
        sort: 'newest',
        limit: '20',
        isFilterOpen: false,
        activeFilterCount: 0,
        tempFilters: mockTempFilters,
        availableBreweries: [{ name: 'Shiga Kogen Beer', flag: '🇯🇵' }],
        availableStyles: ['IPA - New England / Hazy'],
        onMultiSelectChange: vi.fn(),
        onSortChange: vi.fn(),
        onLimitChange: vi.fn(),
        onToggleFilter: vi.fn(),
        onReset: vi.fn(),
        onFilterChange: vi.fn(),
        viewMode: 'individual' as const,
        onViewModeChange: vi.fn(),
        onRefresh: vi.fn()
    };

    it('should trigger onViewModeChange when clicking Grouped / Individual view buttons', () => {
        const handleViewModeChange = vi.fn();
        render(<BeerFilters {...defaultProps} onViewModeChange={handleViewModeChange} />);
        
        fireEvent.click(screen.getByText('Grouped'));
        expect(handleViewModeChange).toHaveBeenCalledWith('grouped');
    });

    it('should trigger onFilterChange when clicking New arrivals toggle (e.g. 24h)', () => {
        const handleFilterChange = vi.fn();
        render(<BeerFilters {...defaultProps} onFilterChange={handleFilterChange} />);

        fireEvent.click(screen.getByText('24h'));
        expect(handleFilterChange).toHaveBeenCalledWith('days', '1');
    });

    it('should trigger onFilterChange when clicking Sale toggle (🔥 セール品)', () => {
        const handleFilterChange = vi.fn();
        render(<BeerFilters {...defaultProps} onFilterChange={handleFilterChange} />);

        fireEvent.click(screen.getByText('🔥 セール品'));
        expect(handleFilterChange).toHaveBeenCalledWith('only_sale', '1');
    });

    it('should show active filter badge on Toggle Filter button when activeFilterCount > 0', () => {
        render(<BeerFilters {...defaultProps} activeFilterCount={3} />);
        expect(screen.getByText('3')).toBeDefined();
    });

    it('should call onToggleFilter when clicking Detailed Filters button', () => {
        const handleToggle = vi.fn();
        render(<BeerFilters {...defaultProps} onToggleFilter={handleToggle} />);

        fireEvent.click(screen.getByText(/Detailed Filters/));
        expect(handleToggle).toHaveBeenCalled();
    });

    it('should trigger onSortChange when selecting a new sort option', () => {
        const handleSortChange = vi.fn();
        render(<BeerFilters {...defaultProps} onSortChange={handleSortChange} />);

        const sortSelect = screen.getByDisplayValue('Newest');
        fireEvent.change(sortSelect, { target: { value: 'price_asc' } });
        expect(handleSortChange).toHaveBeenCalled();
    });
});

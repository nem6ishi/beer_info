import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MultiSelectDropdown from '../MultiSelectDropdown';

describe('MultiSelectDropdown Unit Tests', () => {
    const mockOptions = [
        { value: 'BeerVolta', label: 'BeerVolta' },
        { value: 'Chouseiya', label: 'Chouseiya' },
        { value: 'Dig The Line', label: 'Dig The Line' }
    ];

    it('should display placeholder when nothing is selected', () => {
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={[]}
                onChange={vi.fn()}
                placeholder="Select Shops"
            />
        );
        expect(screen.getByText('Select Shops')).toBeDefined();
    });

    it('should display selected item label when exactly one item is selected', () => {
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={['BeerVolta']}
                onChange={vi.fn()}
                placeholder="Select Shops"
            />
        );
        expect(screen.getByText('BeerVolta')).toBeDefined();
    });

    it('should display count label when multiple items are selected', () => {
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={['BeerVolta', 'Chouseiya']}
                onChange={vi.fn()}
                placeholder="Select Shops"
            />
        );
        expect(screen.getByText('2 selected')).toBeDefined();
    });

    it('should open dropdown when button is clicked and show all options', () => {
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={[]}
                onChange={vi.fn()}
                placeholder="Select Shops"
            />
        );

        fireEvent.click(screen.getByText('Select Shops'));
        expect(screen.getByText('Chouseiya')).toBeDefined();
        expect(screen.getByText('Dig The Line')).toBeDefined();
    });

    it('should call onChange with added option when toggling unselected item', () => {
        const handleChange = vi.fn();
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={['BeerVolta']}
                onChange={handleChange}
                placeholder="Select Shops"
            />
        );

        fireEvent.click(screen.getByText('BeerVolta'));
        const checkbox = screen.getByLabelText('Chouseiya');
        fireEvent.click(checkbox);

        expect(handleChange).toHaveBeenCalledWith(['BeerVolta', 'Chouseiya']);
    });

    it('should call onChange removing option when toggling already selected item', () => {
        const handleChange = vi.fn();
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={['BeerVolta', 'Chouseiya']}
                onChange={handleChange}
                placeholder="Select Shops"
            />
        );

        fireEvent.click(screen.getByText('2 selected'));
        const checkbox = screen.getByLabelText('BeerVolta');
        fireEvent.click(checkbox);

        expect(handleChange).toHaveBeenCalledWith(['Chouseiya']);
    });

    it('should filter options based on search input when searchable is true', () => {
        render(
            <MultiSelectDropdown
                options={mockOptions}
                selectedValues={[]}
                onChange={vi.fn()}
                placeholder="Select Shops"
                searchable={true}
            />
        );

        fireEvent.click(screen.getByText('Select Shops'));
        const searchInput = screen.getByPlaceholderText('Search...');
        fireEvent.change(searchInput, { target: { value: 'Dig' } });

        expect(screen.getByText('Dig The Line')).toBeDefined();
        expect(screen.queryByText('Chouseiya')).toBeNull();
    });
});

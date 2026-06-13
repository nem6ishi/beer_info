import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import TextFilter from '../TextFilter';

describe('TextFilter', () => {
    it('renders correctly with given value and placeholder', () => {
        render(
            <TextFilter 
                value="Initial" 
                onChange={() => {}} 
                placeholder="Test placeholder" 
            />
        );
        
        const input = screen.getByPlaceholderText('Test placeholder') as HTMLInputElement;
        expect(input).toBeInTheDocument();
        expect(input.value).toBe('Initial');
    });

    it('calls onChange when typing', () => {
        const handleChange = vi.fn();
        render(
            <TextFilter 
                value="" 
                onChange={handleChange} 
                placeholder="Search..." 
            />
        );
        
        const input = screen.getByPlaceholderText('Search...');
        fireEvent.change(input, { target: { value: 'New text' } });
        
        expect(handleChange).toHaveBeenCalledTimes(1);
    });
});

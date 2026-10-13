import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Pagination from '../Pagination';

describe('Pagination Component', () => {
    it('should render page buttons and total items', () => {
        render(
            <Pagination
                currentPage={2}
                totalPages={5}
                totalItems={100}
                onPageChange={vi.fn()}
            />
        );

        expect(screen.getByText('Total: 100 beers')).toBeDefined();
        expect(screen.getByText('2')).toBeDefined();
        expect(screen.getByLabelText('Previous Page')).toBeDefined();
        expect(screen.getByLabelText('Next Page')).toBeDefined();
    });

    it('should navigate to next page when ArrowRight is pressed', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                totalPages={5}
                totalItems={100}
                onPageChange={onPageChange}
            />
        );

        fireEvent.keyDown(window, { key: 'ArrowRight' });
        expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it('should navigate to previous page when ArrowLeft is pressed', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={3}
                totalPages={5}
                totalItems={100}
                onPageChange={onPageChange}
            />
        );

        fireEvent.keyDown(window, { key: 'ArrowLeft' });
        expect(onPageChange).toHaveBeenCalledWith(2);
    });

    it('should not navigate past the last page when ArrowRight is pressed', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={5}
                totalPages={5}
                totalItems={100}
                onPageChange={onPageChange}
            />
        );

        fireEvent.keyDown(window, { key: 'ArrowRight' });
        expect(onPageChange).not.toHaveBeenCalled();
    });

    it('should not navigate before the first page when ArrowLeft is pressed', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={1}
                totalPages={5}
                totalItems={100}
                onPageChange={onPageChange}
            />
        );

        fireEvent.keyDown(window, { key: 'ArrowLeft' });
        expect(onPageChange).not.toHaveBeenCalled();
    });

    it('should not navigate when user is typing in an input field', () => {
        const onPageChange = vi.fn();
        render(
            <div>
                <input data-testid="search-input" />
                <Pagination
                    currentPage={2}
                    totalPages={5}
                    totalItems={100}
                    onPageChange={onPageChange}
                />
            </div>
        );

        const input = screen.getByTestId('search-input');
        input.focus();

        fireEvent.keyDown(window, { key: 'ArrowRight' });
        expect(onPageChange).not.toHaveBeenCalled();

        fireEvent.keyDown(window, { key: 'ArrowLeft' });
        expect(onPageChange).not.toHaveBeenCalled();
    });

    it('should not navigate when modifier keys are pressed', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                totalPages={5}
                totalItems={100}
                onPageChange={onPageChange}
            />
        );

        fireEvent.keyDown(window, { key: 'ArrowRight', metaKey: true });
        fireEvent.keyDown(window, { key: 'ArrowRight', ctrlKey: true });
        fireEvent.keyDown(window, { key: 'ArrowRight', altKey: true });
        fireEvent.keyDown(window, { key: 'ArrowRight', shiftKey: true });

        expect(onPageChange).not.toHaveBeenCalled();
    });

    it('should call onPageChange when clicking Prev and Next buttons', () => {
        const onPageChange = vi.fn();
        render(
            <Pagination
                currentPage={2}
                totalPages={5}
                totalItems={100}
                onPageChange={onPageChange}
            />
        );

        fireEvent.click(screen.getByLabelText('Next Page'));
        expect(onPageChange).toHaveBeenCalledWith(3);

        fireEvent.click(screen.getByLabelText('Previous Page'));
        expect(onPageChange).toHaveBeenCalledWith(1);
    });
});

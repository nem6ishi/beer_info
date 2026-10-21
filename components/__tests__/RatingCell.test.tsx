import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RatingCell from '../cells/RatingCell';

describe('RatingCell', () => {
    it('renders untappd link and rating when valid url and rating are provided', () => {
        render(
            <RatingCell
                rating={4.12}
                count={150}
                url="https://untappd.com/b/test/123"
                productType="beer"
            />
        );

        expect(screen.getByText('4.12')).toBeInTheDocument();
        expect(screen.getByText('(150)')).toBeInTheDocument();
        const link = screen.getByRole('link');
        expect(link).toHaveAttribute('href', 'https://untappd.com/b/test/123');
    });

    it('renders "未登録" badge when no untappd url or rating is provided', () => {
        render(
            <RatingCell
                rating={null}
                count={null}
                url={null}
                productType="beer"
            />
        );

        expect(screen.getByText('未登録')).toBeInTheDocument();
        expect(screen.queryByText(/時点$/)).not.toBeInTheDocument();
    });

    it('renders enriched date when enrichedAt timestamp is provided for unlisted beer', () => {
        render(
            <RatingCell
                rating={null}
                count={null}
                url={null}
                productType="beer"
                enrichedAt="2026-10-14T18:53:35.282735+00:00"
            />
        );

        expect(screen.getByText('未登録')).toBeInTheDocument();
        // Since local time may be 10/14 or 10/15 depending on tz, match pattern YYYY/MM/DD時点
        const dateElement = screen.getByText(/2026\/10\/\d{2}時点/);
        expect(dateElement).toBeInTheDocument();
        expect(dateElement).toHaveClass('unlisted-date');
    });
});

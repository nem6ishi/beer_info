import React from 'react'

interface PaginationProps {
    currentPage: number;
    totalPages: number;
    totalItems: number;
    onPageChange: (page: number) => void;
}

export default function Pagination({ currentPage, totalPages, totalItems, onPageChange }: PaginationProps) {
    return (
        <div className="pagination-wrapper">
            <div className="total-count">
                Total: {totalItems?.toLocaleString() || 0} beers
            </div>
            {totalPages > 1 && (
                <div className="pagination-controls">
                    {/* First Page */}
                    <button
                        className="page-btn icon-btn"
                        disabled={currentPage <= 1}
                        onClick={() => onPageChange(1)}
                        aria-label="First Page"
                    >
                        «
                    </button>

                    {/* Previous */}
                    <button
                        className="page-btn"
                        disabled={currentPage <= 1}
                        onClick={() => onPageChange(currentPage - 1)}
                    >
                        ‹ Prev
                    </button>

                    {/* Page Numbers */}
                    <div className="page-numbers">
                        {(() => {
                            const pages: (number | string)[] = [];
                            const maxVisible = 7;

                            if (totalPages <= maxVisible) {
                                for (let i = 1; i <= totalPages; i++) pages.push(i);
                            } else {
                                pages.push(1);

                                let start = Math.max(2, currentPage - 1);
                                let end = Math.min(totalPages - 1, currentPage + 1);

                                if (currentPage <= 3) {
                                    end = 4;
                                }
                                if (currentPage >= totalPages - 2) {
                                    start = totalPages - 3;
                                }

                                if (start > 2) {
                                    pages.push('...');
                                }

                                for (let i = start; i <= end; i++) {
                                    pages.push(i);
                                }

                                if (end < totalPages - 1) {
                                    pages.push('...');
                                }

                                pages.push(totalPages);
                            }

                            return pages.map((p, idx) => (
                                p === '...' ? (
                                    <span key={`ellipsis-${idx}`} className="page-ellipsis">...</span>
                                ) : (
                                    <button
                                        key={p}
                                        className={`page-number ${p === currentPage ? 'active' : ''}`}
                                        onClick={() => onPageChange(p as number)}
                                    >
                                        {p}
                                    </button>
                                )
                            ));
                        })()}
                    </div>

                    {/* Next */}
                    <button
                        className="page-btn"
                        disabled={currentPage >= totalPages}
                        onClick={() => onPageChange(currentPage + 1)}
                    >
                        Next ›
                    </button>

                    {/* Last Page */}
                    <button
                        className="page-btn icon-btn"
                        disabled={currentPage >= totalPages}
                        onClick={() => onPageChange(totalPages)}
                        aria-label="Last Page"
                    >
                        »
                    </button>
                </div>
            )}
        </div>
    )
}

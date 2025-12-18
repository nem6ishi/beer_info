import React from 'react'

export default function Pagination({ currentPage, totalPages, totalItems, onPageChange }) {
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
                            const pages = [];
                            const maxVisible = 7; // Total number of slots (1, ..., 4, 5, 6, ..., 100)

                            if (totalPages <= maxVisible) {
                                for (let i = 1; i <= totalPages; i++) pages.push(i);
                            } else {
                                // Always show 1
                                pages.push(1);

                                // Determine start and end of sliding window
                                let start = Math.max(2, currentPage - 1);
                                let end = Math.min(totalPages - 1, currentPage + 1);

                                // Adjust if at edges
                                if (currentPage <= 3) {
                                    end = 4; // 1, 2, 3, 4 ...
                                }
                                if (currentPage >= totalPages - 2) {
                                    start = totalPages - 3; // ... 97, 98, 99, 100
                                }

                                // Add left ellipsis
                                if (start > 2) {
                                    pages.push('...');
                                }

                                // Add window
                                for (let i = start; i <= end; i++) {
                                    pages.push(i);
                                }

                                // Add right ellipsis
                                if (end < totalPages - 1) {
                                    pages.push('...');
                                }

                                // Always show last
                                pages.push(totalPages);
                            }

                            return pages.map((p, idx) => (
                                p === '...' ? (
                                    <span key={`ellipsis-${idx}`} className="page-ellipsis">...</span>
                                ) : (
                                    <button
                                        key={p}
                                        className={`page-number ${p === currentPage ? 'active' : ''}`}
                                        onClick={() => onPageChange(p)}
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

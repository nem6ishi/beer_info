import { BeerAPI } from './js/api.js';
import { BeerUI } from './js/ui.js';
import { debounce } from './js/utils.js';

document.addEventListener('DOMContentLoaded', () => {
    const api = new BeerAPI();
    const ui = new BeerUI('beerTableBody', 'statusMessage');
    const searchInput = document.getElementById('searchInput');
    const sortSelect = document.getElementById('sortSelect');

    let currentPage = 1;
    let currentSearch = '';
    let currentSort = 'newest';
    let totalBeers = 0;
    let totalPages = 0;

    const loadPage = async (page, search = '', sort = 'newest') => {
        try {
            ui.setLoading(true);
            const response = await api.fetchBeers(page, 30, search, sort);

            ui.render(response.beers);
            totalBeers = response.pagination.total;
            totalPages = response.pagination.totalPages;

            updatePagination(response.pagination);
            ui.setLoading(false);
        } catch (error) {
            ui.showError('Error loading beers. Please try again later.');
            console.error(error);
        }
    };

    const updatePagination = (pagination) => {
        const { page, total, totalPages } = pagination;
        const paginationContainer = document.getElementById('pagination');

        if (totalPages <= 1) {
            paginationContainer.innerHTML = '';
            return;
        }

        let html = '<div class="pagination-controls">';

        // First page button
        if (page > 1) {
            html += `<button class="page-btn first-last-btn" data-page="1" title="First page">⏮ First</button>`;
        }

        // Previous button
        if (page > 1) {
            html += `<button class="page-btn" data-page="${page - 1}">← Previous</button>`;
        }

        // Page numbers with smart ellipsis
        html += '<div class="page-numbers">';
        const pageNumbers = generatePageNumbers(page, totalPages);
        pageNumbers.forEach(pageNum => {
            if (pageNum === '...') {
                html += '<span class="page-ellipsis">...</span>';
            } else {
                const activeClass = pageNum === page ? ' active' : '';
                html += `<button class="page-number${activeClass}" data-page="${pageNum}">${pageNum}</button>`;
            }
        });
        html += '</div>';

        // Next button
        if (page < totalPages) {
            html += `<button class="page-btn" data-page="${page + 1}">Next →</button>`;
        }

        // Last page button
        if (page < totalPages) {
            html += `<button class="page-btn first-last-btn" data-page="${totalPages}" title="Last page">Last ⏭</button>`;
        }

        // Page jump input
        html += '<div class="page-jump">';
        html += '<span class="page-jump-label">Go to:</span>';
        html += `<input type="number" class="page-jump-input" min="1" max="${totalPages}" value="${page}" placeholder="${page}">`;
        html += '</div>';

        // Page info
        html += '<div class="page-info-bottom">';
        html += `Page ${page} of ${totalPages} <span class="total-items">(${total} beers)</span>`;
        html += '</div>';

        html += '</div>';
        paginationContainer.innerHTML = html;

        // Add event listeners to all pagination buttons
        paginationContainer.querySelectorAll('.page-btn, .page-number').forEach(btn => {
            btn.addEventListener('click', () => {
                const newPage = parseInt(btn.dataset.page);
                currentPage = newPage;
                loadPage(currentPage, currentSearch, currentSort);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        });

        // Add event listener for page jump input
        const pageJumpInput = paginationContainer.querySelector('.page-jump-input');
        pageJumpInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                let newPage = parseInt(pageJumpInput.value);
                if (newPage >= 1 && newPage <= totalPages) {
                    currentPage = newPage;
                    loadPage(currentPage, currentSearch, currentSort);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    pageJumpInput.value = page;
                }
            }
        });
    };

    const generatePageNumbers = (current, total) => {
        const pages = [];

        if (total <= 7) {
            // Show all pages if 7 or fewer
            for (let i = 1; i <= total; i++) {
                pages.push(i);
            }
        } else {
            // Always show first page
            pages.push(1);

            if (current <= 4) {
                // Near the beginning
                for (let i = 2; i <= 5; i++) {
                    pages.push(i);
                }
                pages.push('...');
                pages.push(total);
            } else if (current >= total - 3) {
                // Near the end
                pages.push('...');
                for (let i = total - 4; i <= total; i++) {
                    pages.push(i);
                }
            } else {
                // In the middle
                pages.push('...');
                for (let i = current - 1; i <= current + 1; i++) {
                    pages.push(i);
                }
                pages.push('...');
                pages.push(total);
            }
        }

        return pages;
    };

    // Sort Dropdown Listener
    if (sortSelect) {
        sortSelect.addEventListener('change', (e) => {
            currentSort = e.target.value;
            currentPage = 1;
            loadPage(currentPage, currentSearch, currentSort);
        });
    }

    // Search with debounce
    searchInput.addEventListener('input', debounce((e) => {
        currentSearch = e.target.value;
        currentPage = 1;
        loadPage(currentPage, currentSearch, currentSort);
    }, 300));

    // Initial load
    loadPage(currentPage, currentSearch, currentSort);
});

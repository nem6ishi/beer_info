import { BeerAPI } from './js/api.js';
import { BeerUI } from './js/ui.js';
import { getSortableTime, debounce } from './js/utils.js';

document.addEventListener('DOMContentLoaded', () => {
    const api = new BeerAPI();
    const ui = new BeerUI('beerTableBody', 'statusMessage');
    const searchInput = document.getElementById('searchInput');

    let allBeers = [];
    let filteredBeers = [];
    let currentPage = 1;
    const itemsPerPage = 100;

    const renderPage = (beers, page) => {
        const start = (page - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const pageBeers = beers.slice(start, end);

        ui.render(pageBeers);
        updatePagination(beers.length, page);
    };

    const updatePagination = (totalItems, page) => {
        const totalPages = Math.ceil(totalItems / itemsPerPage);
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
        html += `Page ${page} of ${totalPages} <span class="total-items">(${totalItems} beers)</span>`;
        html += '</div>';

        html += '</div>';
        paginationContainer.innerHTML = html;

        // Add event listeners to all pagination buttons
        paginationContainer.querySelectorAll('.page-btn, .page-number').forEach(btn => {
            btn.addEventListener('click', () => {
                const newPage = parseInt(btn.dataset.page);
                currentPage = newPage;
                renderPage(filteredBeers, currentPage);
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
                    renderPage(filteredBeers, currentPage);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    pageJumpInput.value = page;
                }
            }
        });

        // Keyboard navigation
        document.removeEventListener('keydown', handleKeyboardNavigation);
        document.addEventListener('keydown', handleKeyboardNavigation);
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

    const handleKeyboardNavigation = (e) => {
        // Only handle arrow keys when not typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        const totalPages = Math.ceil(filteredBeers.length / itemsPerPage);

        if (e.key === 'ArrowLeft' && currentPage > 1) {
            e.preventDefault();
            currentPage--;
            renderPage(filteredBeers, currentPage);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else if (e.key === 'ArrowRight' && currentPage < totalPages) {
            e.preventDefault();
            currentPage++;
            renderPage(filteredBeers, currentPage);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };

    const parsePrice = (priceStr) => {
        if (!priceStr) return 0;
        // Extract number from string like "1,460円" -> 1460
        const match = priceStr.match(/(\d{1,3}(,\d{3})*)/);
        return match ? parseInt(match[0].replace(/,/g, '')) : 0;
    };

    const parseABV = (abvStr) => {
        if (!abvStr || abvStr === 'N/A') return -1;
        return parseFloat(abvStr.replace('%', ''));
    };

    const parseRating = (ratingStr) => {
        if (!ratingStr || ratingStr === 'N/A') return -1;
        return parseFloat(ratingStr);
    };

    // Sort function
    const sortBeers = (beers, criteria) => {
        const sorted = [...beers];

        switch (criteria) {
            case 'newest':
                sorted.sort((a, b) => {
                    if (a._scrapeTimestamp !== b._scrapeTimestamp) {
                        return b._scrapeTimestamp.localeCompare(a._scrapeTimestamp);
                    }
                    return a._scrapeOrder - b._scrapeOrder;
                });
                break;
            case 'price_asc':
                sorted.sort((a, b) => parsePrice(a.price) - parsePrice(b.price));
                break;
            case 'price_desc':
                sorted.sort((a, b) => parsePrice(b.price) - parsePrice(a.price));
                break;
            case 'abv_desc':
                sorted.sort((a, b) => parseABV(b.untappd_abv) - parseABV(a.untappd_abv));
                break;
            case 'rating_desc':
                sorted.sort((a, b) => parseRating(b.untappd_rating) - parseRating(a.untappd_rating));
                break;
            case 'name_asc':
                sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
                break;
            default:
                // Default to newest
                sorted.sort((a, b) => {
                    if (a._scrapeTimestamp !== b._scrapeTimestamp) {
                        return b._scrapeTimestamp.localeCompare(a._scrapeTimestamp);
                    }
                    return a._scrapeOrder - b._scrapeOrder;
                });
        }
        return sorted;
    };

    const init = async () => {
        try {
            const data = await api.fetchBeers();

            // Process and Sort
            allBeers = data.map(beer => ({
                ...beer,
                _sortTime: getSortableTime(beer),
                _scrapeOrder: beer.scrape_order !== undefined ? beer.scrape_order : 999999,
                _scrapeTimestamp: beer.scrape_timestamp || ''
            }));

            // Initial sort (Newest)
            filteredBeers = sortBeers(allBeers, 'newest');

            renderPage(filteredBeers, currentPage);
            ui.setLoading(false);

            // Sort Dropdown Listener
            const sortSelect = document.getElementById('sortSelect');
            if (sortSelect) {
                sortSelect.addEventListener('change', (e) => {
                    const sortValue = e.target.value;
                    // Sort the currently filtered list if search is active, or allBeers
                    // Re-sorting allBeers and then re-filtering might be cleaner but 
                    // sorting filteredBeers respects the current search result set.
                    // However, standard UX usually implies sorting applies to the view.

                    // Let's sort filteredBeers to keep search results
                    filteredBeers = sortBeers(filteredBeers, sortValue);
                    currentPage = 1;
                    renderPage(filteredBeers, currentPage);
                });
            }

        } catch (error) {
            ui.showError('Error loading beers. Please try again later.');
            console.error(error);
        }
    };

    // Search with debounce to improve performance
    searchInput.addEventListener('input', debounce((e) => {
        const term = e.target.value.toLowerCase();
        // Filter from full list
        const searchResults = allBeers.filter(beer =>
            (beer.name && beer.name.toLowerCase().includes(term)) ||
            (beer.brewery && beer.brewery.toLowerCase().includes(term)) ||
            (beer.beer_name_clean && beer.beer_name_clean.toLowerCase().includes(term))
        );

        // Re-apply current sort
        const sortSelect = document.getElementById('sortSelect');
        const currentSort = sortSelect ? sortSelect.value : 'newest';

        filteredBeers = sortBeers(searchResults, currentSort);
        currentPage = 1;
        renderPage(filteredBeers, currentPage);
    }, 300));

    init();
});


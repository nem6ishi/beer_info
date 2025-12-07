import { formatPrice, formatTime } from './utils.js';

export class BeerUI {
    constructor(tableBodyId, statusMessageId) {
        this.tableBody = document.getElementById(tableBodyId);
        this.statusMessage = document.getElementById(statusMessageId);
    }

    setLoading(isLoading) {
        if (this.statusMessage) {
            this.statusMessage.style.display = isLoading ? 'block' : 'none';
        }
    }

    showError(msg) {
        if (this.statusMessage) {
            this.statusMessage.textContent = msg;
            this.statusMessage.style.display = 'block';
        }
    }

    render(beers) {
        this.tableBody.innerHTML = '';

        if (beers.length === 0) {
            this.tableBody.innerHTML = '<tr><td colspan="7" class="status-message">No beers found.</td></tr>';
            return;
        }

        const fragment = document.createDocumentFragment();

        beers.forEach(beer => {
            const row = document.createElement('tr');
            row.className = 'beer-row';
            row.innerHTML = this.buildRowHTML(beer);
            fragment.appendChild(row);
        });

        this.tableBody.appendChild(fragment);
    }

    buildStockBadge(beer) {
        let stockClass = 'badge-stock-in';
        let stockText = 'In Stock';
        const statusLower = (beer.stock_status || '').toLowerCase();

        if (statusLower.includes('sold') || statusLower.includes('out')) {
            stockClass = 'badge-stock-out';
            stockText = 'Sold Out';
        } else if (statusLower.includes('pre') || statusLower.includes('upcoming')) {
            stockClass = 'badge-stock-pre';
            stockText = 'Pre-Order';
        }

        return { stockClass, stockText };
    }

    buildNameCell(beer) {
        const brewery = beer.untappd_brewery_name || beer.brewery || '';
        const cleanName = beer.untappd_beer_name || beer.beer_name_clean || beer.name;

        if (brewery && cleanName && cleanName !== 'Unknown') {
            return `
                <div class="meta-brewery">${this.escapeHtml(brewery)}</div>
                <div class="meta-name" title="${this.escapeHtml(beer.name)}">${this.escapeHtml(cleanName)}</div>
            `;
        }
        return `<div class="meta-name">${this.escapeHtml(beer.name)}</div>`;
    }

    buildStyleCell(beer) {
        const style = beer.untappd_style || '';
        const abv = beer.untappd_abv && beer.untappd_abv !== 'N/A' ? beer.untappd_abv : 'N/A';
        const ibu = beer.untappd_ibu && beer.untappd_ibu !== 'N/A' ? beer.untappd_ibu : 'N/A';

        let html = '';
        if (style) {
            html += `<div class="meta-style-primary">${this.escapeHtml(style)}</div>`;
        } else {
            html += '<span class="no-data">N/A</span>';
        }

        html += `
            <div class="stats-row">
                <span class="stat-tag abv">${abv} ABV</span>
                <span class="stat-tag ibu">${ibu} IBU</span>
            </div>`;

        return html;
    }

    buildUntappdCell(beer) {
        if (!beer.untappd_url) {
            return '<span class="no-link">N/A</span>';
        }

        const rating = beer.untappd_rating && beer.untappd_rating !== 'N/A' ? beer.untappd_rating : 'N/A';
        let fetchedHtml = '';

        if (beer.untappd_fetched_at) {
            try {
                const dateObj = new Date(beer.untappd_fetched_at);
                const dateStr = dateObj.toLocaleDateString();
                fetchedHtml = `<div class="untappd-fetched">Checked: ${dateStr}</div>`;
            } catch (e) {
                // ignore invalid date
            }
        }

        return `
            <div class="untappd-wrapper">
                <a href="${beer.untappd_url}" target="_blank" rel="noopener noreferrer" class="untappd-btn">
                    Untappd
                </a>
                <div class="untappd-rating">
                    <span class="star">★</span> ${rating} <span class="count">(${beer.untappd_rating_count || 0})</span>
                </div>
                ${fetchedHtml}
            </div>
        `;
    }

    buildShopCell(beer) {
        const { stockClass, stockText } = this.buildStockBadge(beer);
        const lastSeen = formatTime(beer.last_seen || beer.first_seen || beer._displayTime);
        const showChecked = beer.last_seen && beer.last_seen !== beer.first_seen;
        const cleanName = beer.untappd_beer_name || beer.beer_name_clean || beer.name; // Used for alt text

        return `
            <div class="shop-wrapper">
                <a href="${beer.url}" target="_blank" rel="noopener noreferrer" class="shop-btn">
                    ${this.escapeHtml(beer.shop || 'Shop')}
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                </a>
                <span class="badge ${stockClass}">${stockText}</span>
                ${showChecked ? `<div class="shop-checked">Checked: ${lastSeen.date}</div>` : ''}
            </div>
        `;
    }

    buildRegisteredCell(beer) {
        // available_since: 購入可能日時（再入荷時は再入荷日、初回はfirst_seen）
        const availableSince = formatTime(beer.available_since || beer.first_seen || beer._displayTime);
        return `<div class="registered-date">${availableSince.date}</div>`;
    }

    buildRowHTML(beer) {
        const cleanName = beer.untappd_beer_name || beer.beer_name_clean || beer.name;
        const price = formatPrice(beer.price || '0円');

        return `
            <td class="col-img">
                <div class="img-container">
                    <img src="${beer.image}" alt="${this.escapeHtml(cleanName)}" loading="lazy">
                </div>
            </td>
            <td class="col-name">
                ${this.buildNameCell(beer)}
            </td>
            <td class="col-style">
                ${this.buildStyleCell(beer)}
            </td>
            <td class="col-untappd">
                ${this.buildUntappdCell(beer)}
            </td>
            <td class="col-price">${price}</td>
            <td class="col-shop">
                ${this.buildShopCell(beer)}
            </td>
            <td class="col-registered">
                ${this.buildRegisteredCell(beer)}
            </td>
        `;
    }

    escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

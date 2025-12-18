import React from 'react'
import MultiSelectDropdown from './MultiSelectDropdown'

export default function BeerFilters({
    shop,
    brewery_filter,
    style_filter,
    sort,
    limit,
    isFilterOpen,
    activeFilterCount,
    tempFilters,
    availableBreweries,
    availableStyles,
    onMultiSelectChange,
    onSortChange,
    onLimitChange,
    onToggleFilter,
    onReset,
    onFilterChange,
    shopCounts = {},

    viewMode = 'individual', // 'individual' or 'grouped'
    onViewModeChange,
    onRefresh
}) {
    return (
        <>
            <div className="controls-bar">
                {/* View Toggle */}
                <div className="filter-group-main">
                    <label className="sort-label">View:</label>
                    <div className="view-toggle-group">
                        <button
                            className={`view-toggle-btn ${viewMode === 'individual' ? 'active' : ''}`}
                            onClick={() => onViewModeChange('individual')}
                        >
                            Individual
                        </button>
                        <button
                            className={`view-toggle-btn ${viewMode === 'grouped' ? 'active' : ''}`}
                            onClick={() => onViewModeChange('grouped')}
                        >
                            Grouped
                        </button>
                    </div>
                </div>

                <div className="filter-group-main">
                    <label className="sort-label">Store:</label>
                    <MultiSelectDropdown
                        options={Object.entries(shopCounts)
                            .map(([name, count]) => ({ value: name, label: `${name} (${count})`, count }))
                            .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
                        }
                        selectedValues={shop ? shop.split(',') : []}
                        onChange={(vals) => onMultiSelectChange('shop', vals)}
                        placeholder="Select Stores"
                    />
                </div>

                {/* Breweries Dropdown (Multi-select) */}
                <div className="filter-group-main">
                    <button className="dropdown-toggle" style={{ display: 'none' }}>Breweries</button>
                    <label className="sort-label">Breweries:</label>
                    <MultiSelectDropdown
                        options={availableBreweries.map(b => ({
                            label: b.name,
                            value: b.name,
                            flag: b.flag
                        }))}
                        selectedValues={brewery_filter ? brewery_filter.split(',') : []}
                        onChange={(vals) => onMultiSelectChange('brewery_filter', vals)}
                        placeholder="Select Breweries"
                        searchable={true}
                    />
                </div>

                {/* Style Dropdown (Multi-select) */}
                <div className="filter-group-main">
                    <label className="sort-label">Style:</label>
                    <MultiSelectDropdown
                        options={availableStyles.map(s => ({
                            value: typeof s === 'string' ? s : s.style,
                            label: typeof s === 'string' ? s : `${s.style} (${s.count})`
                        }))}
                        selectedValues={style_filter ? style_filter.split(',') : []}
                        onChange={(vals) => onMultiSelectChange('style_filter', vals)}
                        placeholder="Select Styles"
                        searchable={true}
                    />
                </div>

                {/* Sort (Main Bar) */}
                <div className="filter-group-main">
                    <label htmlFor="sortSelect" className="sort-label">Sort:</label>
                    <div className="select-wrapper">
                        <select
                            id="sortSelect"
                            className="sort-select"
                            value={sort}
                            onChange={onSortChange}
                            aria-label="Sort beers"
                        >
                            <option value="newest">Newest</option>
                            <option value="price_asc">Price: Low to High</option>
                            <option value="price_desc">Price: High to Low</option>
                            <option value="abv_desc">ABV: High to Low</option>
                            <option value="rating_desc">Rating: High to Low</option>
                            <option value="name_asc">Name: A to Z</option>
                        </select>
                    </div>
                </div>

                {/* Limit Filter */}
                <div className="filter-group-main">
                    <label htmlFor="limitSelect" className="sort-label">Limit:</label>
                    <div className="select-wrapper">
                        <select
                            id="limitSelect"
                            className="sort-select"
                            value={limit}
                            onChange={onLimitChange}
                            aria-label="Items per page"
                            style={{ minWidth: '80px' }}
                        >
                            <option value="20">20</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </select>
                    </div>
                </div>

                <div className="controls-divider"></div>

                {/* Advanced Toggle */}
                <button
                    className={`open-filter-btn ${isFilterOpen ? 'active' : ''}`}
                    onClick={onToggleFilter}
                    aria-expanded={isFilterOpen}
                >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                    </svg>
                    Detailed Filters
                    {activeFilterCount > 0 && <span className="filter-badge-count">{activeFilterCount}</span>}
                    <span className="toggle-icon">{isFilterOpen ? '▲' : '▼'}</span>
                </button>

                {/* Reset Button (Always visible) */}
                <div className="controls-divider"></div>
                <button
                    className="reset-btn-small"
                    onClick={onReset}
                    title="Reset all filters"
                >
                    Reset
                </button>
                <button
                    className="reset-btn-small refresh-btn"
                    onClick={onRefresh}
                    title="Refresh List"
                >
                    ↻
                </button>
            </div>

            {/* Collapsible Filter Area */}
            <div className={`filter-collapsible ${isFilterOpen ? 'open' : ''}`}>
                <div className="filter-content">
                    <div className="filter-grid">

                        {/* ABV Filter */}
                        <div className="filter-item">
                            <label>ABV (%)</label>
                            <div className="input-range-group">
                                <input
                                    type="number"
                                    className="filter-input"
                                    placeholder="Min"
                                    value={tempFilters.min_abv}
                                    onChange={(e) => onFilterChange('min_abv', e.target.value)}
                                />
                                <span>-</span>
                                <input
                                    type="number"
                                    className="filter-input"
                                    placeholder="Max"
                                    value={tempFilters.max_abv}
                                    onChange={(e) => onFilterChange('max_abv', e.target.value)}
                                />
                            </div>
                        </div>

                        {/* IBU Filter */}
                        <div className="filter-item">
                            <label>IBU</label>
                            <div className="input-range-group">
                                <input
                                    type="number"
                                    className="filter-input"
                                    placeholder="Min"
                                    value={tempFilters.min_ibu}
                                    onChange={(e) => onFilterChange('min_ibu', e.target.value)}
                                />
                                <span>-</span>
                                <input
                                    type="number"
                                    className="filter-input"
                                    placeholder="Max"
                                    value={tempFilters.max_ibu}
                                    onChange={(e) => onFilterChange('max_ibu', e.target.value)}
                                />
                            </div>
                        </div>

                        {/* Rating Filter */}
                        <div className="filter-item">
                            <label>Rating (Min)</label>
                            <input
                                type="number"
                                step="0.1"
                                className="filter-input"
                                placeholder="0-5"
                                value={tempFilters.min_rating}
                                onChange={(e) => onFilterChange('min_rating', e.target.value)}
                            />
                        </div>

                        {/* Stock Filter */}
                        <div className="filter-item">
                            <label>Stock</label>
                            <div className="select-wrapper full-width">
                                <select
                                    className="filter-select"
                                    value={tempFilters.stock_filter}
                                    onChange={(e) => onFilterChange('stock_filter', e.target.value)}
                                >
                                    <option value="">All</option>
                                    <option value="in_stock">In Stock Only</option>
                                    <option value="sold_out">Sold Out Only</option>
                                </select>
                            </div>
                        </div>

                        {/* Set Product Filter */}
                        <div className="filter-item">
                            <label>Product Type</label>
                            <div className="select-wrapper full-width">
                                <select
                                    className="filter-select"
                                    value={tempFilters.set_mode || ''}
                                    onChange={(e) => onFilterChange('set_mode', e.target.value)}
                                >
                                    <option value="">All Products</option>
                                    <option value="individual">Individual Beers Only</option>
                                    <option value="set">Sets Only</option>
                                </select>
                            </div>
                        </div>

                        {/* Untappd Status Filter */}
                        <div className="filter-item">
                            <label>Untappd Status</label>
                            <div className="select-wrapper full-width">
                                <select
                                    className="filter-select"
                                    value={tempFilters.untappd_status || ''}
                                    onChange={(e) => onFilterChange('untappd_status', e.target.value)}
                                >
                                    <option value="">All</option>
                                    <option value="linked">Has Untappd Link</option>
                                    <option value="missing">Missing Untappd Link</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    )
}

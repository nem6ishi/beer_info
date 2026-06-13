import React, { ChangeEvent } from 'react'
import MultiSelectDropdown from './MultiSelectDropdown'
import FilterSection from './filters/FilterSection'
import RangeFilter from './filters/RangeFilter'
import type { FilterState, SelectOption, BreweryOption, StyleOption } from '../types/beer'

interface BeerFiltersProps {
    shop: string;
    shopCounts: Record<string, number>;
    brewery_filter: string;
    style_filter: string;
    sort: string;
    limit: string;
    isFilterOpen: boolean;
    activeFilterCount: number;
    tempFilters: FilterState;
    availableBreweries: BreweryOption[];
    availableStyles: (string | StyleOption)[];
    onMultiSelectChange: (key: string, values: string[]) => void;
    onSortChange: (e: ChangeEvent<HTMLSelectElement>) => void;
    onLimitChange: (e: ChangeEvent<HTMLSelectElement>) => void;
    onToggleFilter: () => void;
    onReset: () => void;
    onFilterChange: (key: string, value: string) => void;
    viewMode?: 'individual' | 'grouped';
    onViewModeChange: (mode: string) => void;
    onRefresh: () => void;
}

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

    viewMode = 'individual',
    onViewModeChange,
    onRefresh
}: BeerFiltersProps) {
    return (
        <>
            <div className="controls-bar">
                {/* View Toggle */}
                <FilterSection label="View:">
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
                </FilterSection>

                {/* Store Dropdown */}
                <FilterSection label="Store:">
                    <MultiSelectDropdown
                        options={Object.entries(shopCounts)
                            .map(([name, count]): SelectOption => ({ value: name, label: `${name} (${count})`, count }))
                            .sort((a, b) => (b.count ?? 0) - (a.count ?? 0) || a.value.localeCompare(b.value))
                        }
                        selectedValues={shop ? shop.split(',') : []}
                        onChange={(vals) => onMultiSelectChange('shop', vals)}
                        placeholder="Select Stores"
                    />
                </FilterSection>

                {/* Breweries Dropdown (Multi-select) */}
                <FilterSection label="Breweries:">
                    <button className="dropdown-toggle" style={{ display: 'none' }}>Breweries</button>
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
                </FilterSection>

                {/* Style Dropdown (Multi-select) */}
                <FilterSection label="Style:">
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
                </FilterSection>

                {/* Sort (Main Bar) */}
                <FilterSection label="Sort:" htmlFor="sortSelect">
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
                </FilterSection>

                {/* Limit Filter */}
                <FilterSection label="Limit:" htmlFor="limitSelect">
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
                </FilterSection>

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
                        <FilterSection label="ABV (%)" className="filter-item">
                            <RangeFilter
                                minValue={tempFilters.min_abv}
                                maxValue={tempFilters.max_abv}
                                onMinChange={(val) => onFilterChange('min_abv', val)}
                                onMaxChange={(val) => onFilterChange('max_abv', val)}
                            />
                        </FilterSection>

                        {/* IBU Filter */}
                        <FilterSection label="IBU" className="filter-item">
                            <RangeFilter
                                minValue={tempFilters.min_ibu}
                                maxValue={tempFilters.max_ibu}
                                onMinChange={(val) => onFilterChange('min_ibu', val)}
                                onMaxChange={(val) => onFilterChange('max_ibu', val)}
                            />
                        </FilterSection>

                        {/* Rating Filter */}
                        <FilterSection label="Rating (Min)" className="filter-item">
                            <RangeFilter
                                minValue={tempFilters.min_rating}
                                onMinChange={(val) => onFilterChange('min_rating', val)}
                                showMax={false}
                                step="0.1"
                                minPlaceholder="0-5"
                            />
                        </FilterSection>

                        {/* Stock Filter */}
                        <FilterSection label="Stock" className="filter-item">
                            <div className="select-wrapper full-width">
                                <select
                                    className="filter-select"
                                    value={tempFilters.stock_filter}
                                    onChange={(e) => onFilterChange('stock_filter', e.target.value)}
                                >
                                    <option value="all">All</option>
                                    <option value="in_stock">In Stock Only</option>
                                    <option value="sold_out">Sold Out Only</option>
                                </select>
                            </div>
                        </FilterSection>

                        {/* Product Type Filter */}
                        <FilterSection label="Product Type" className="filter-item">
                            <div className="select-wrapper full-width">
                                <select
                                    className="filter-select"
                                    value={tempFilters.product_type || ''}
                                    onChange={(e) => onFilterChange('product_type', e.target.value)}
                                >
                                    <option value="">All Products</option>
                                    <option value="beer">Individual Beers</option>
                                    <option value="set">Sets</option>
                                    <option value="glass">Glassware</option>
                                    <option value="other">Merch / Others</option>
                                </select>
                            </div>
                        </FilterSection>

                        {/* Untappd Status Filter */}
                        <FilterSection label="Untappd Status" className="filter-item">
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
                        </FilterSection>

                        {/* Debug Mode Filter */}
                        <FilterSection label="Debug Mode" className="filter-item">
                            <div className="checkbox-wrapper" style={{ display: 'flex', alignItems: 'center', height: '100%', gap: '8px', paddingLeft: '4px' }}>
                                <input
                                    type="checkbox"
                                    id="debugToggle"
                                    checked={tempFilters.debug === '1'}
                                    onChange={(e) => onFilterChange('debug', e.target.checked ? '1' : '')}
                                    style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                                />
                                <label htmlFor="debugToggle" style={{ margin: 0, cursor: 'pointer', fontWeight: 'normal', color: 'var(--text-main, #333)' }}>
                                    Show Original Names
                                </label>
                            </div>
                        </FilterSection>
                    </div>
                </div>
            </div>
        </>
    )
}

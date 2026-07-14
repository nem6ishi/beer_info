"use client";

import React, { useEffect } from 'react'
import Link from 'next/link'
import GroupedBeerTable from './GroupedBeerTable'
import Pagination from './Pagination'
import BeerFilters from './BeerFilters'
import { useBeerFilters } from '../hooks/useBeerFilters'
import { useBeerData } from '../hooks/useBeerData'
import type { GroupedBeer, BreweryOption, StyleOption, GroupedBeersApiResponse } from '../types/beer'

interface GroupedClientProps {
    initialData: GroupedBeersApiResponse;
    availableStyles: (string | StyleOption)[];
    availableBreweries: BreweryOption[];
}

export default function GroupedClient({ initialData, availableStyles, availableBreweries }: GroupedClientProps) {
    const {
        searchInput,
        isFilterOpen,
        setIsFilterOpen,
        tempFilters,
        isPending,
        updateURL,
        handleSearchChange,
        handleFilterChange,
        handleMultiSelectChange,
        resetFilters,
        syncFiltersFromParams,
        searchParams,
    } = useBeerFilters();

    const {
        data: groups,
        shopCounts,
        loading,
        error,
        totalPages,
        totalItems,
        fetchData,
        syncDataFromInitial
    } = useBeerData<GroupedBeer[], GroupedBeersApiResponse>({
        initialData,
        endpoint: '/api/grouped-beers',
        dataKey: 'groups'
    });

    const page = parseInt(searchParams.get('page') || '1', 10);
    const limit = searchParams.get('limit') || '20';
    const sort = searchParams.get('sort') || 'newest';

    useEffect(() => {
        const hasFilters = Array.from(searchParams.keys()).length > 0;
        
        if (hasFilters) {
            // URL has parameters, fetch client-side
            fetchData();
        } else {
            // No parameters, use the instantly loaded static default data
            syncDataFromInitial();
        }
        
        syncFiltersFromParams();
    }, [initialData, searchParams, fetchData, syncDataFromInitial, syncFiltersFromParams]);

    const handlePageChange = (newPage: number) => updateURL({ page: newPage.toString() });

    return (
        <>
            <header className="glass-header">
                <div className="container header-content">
                    <h1>
                        <Link href="/" onClick={(e) => { e.preventDefault(); resetFilters(); }} style={{ textDecoration: 'none', color: 'inherit' }}>
                            Craft Beer Alert Japan
                        </Link>
                    </h1>
                    <div className="search-bar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                        <input
                            type="text"
                            placeholder="Search beers..."
                            value={searchInput}
                            onChange={handleSearchChange}
                            aria-label="Search for beers"
                        />
                    </div>
                </div>
            </header>

            <main className="container" style={{ minHeight: '80vh' }}>
                <BeerFilters
                    shop={searchParams.get('shop') || ''}
                    shopCounts={shopCounts}
                    brewery_filter={searchParams.get('brewery_filter') || ''}
                    style_filter={searchParams.get('style_filter') || ''}
                    sort={sort}
                    limit={limit}
                    isFilterOpen={isFilterOpen}
                    activeFilterCount={Array.from(searchParams.keys()).length}
                    tempFilters={tempFilters}
                    availableBreweries={availableBreweries}
                    availableStyles={availableStyles}
                    onMultiSelectChange={handleMultiSelectChange}
                    onSortChange={(e) => updateURL({ sort: e.target.value, page: '1' })}
                    onLimitChange={(e) => updateURL({ limit: e.target.value, page: '1' })}
                    onToggleFilter={() => setIsFilterOpen(!isFilterOpen)}
                    onReset={resetFilters}
                    onFilterChange={handleFilterChange}
                    viewMode="grouped"
                    onViewModeChange={(mode) => mode === 'individual' && updateURL({}, '/')}
                    onRefresh={fetchData}
                />

                <div id="results-top" style={{ scrollMarginTop: '120px' }}></div>
                <GroupedBeerTable
                    groups={groups}
                    loading={loading || isPending}
                    error={error}
                    isDebug={searchParams.get('debug') === '1'}
                    stockFilter={(searchParams.get('stock_filter') || 'in_stock') as string}
                    selectedShops={searchParams.get('shop') ? (searchParams.get('shop') as string).split(',') : []}
                />

                {!loading && !error && (
                    <Pagination
                        currentPage={page}
                        totalPages={totalPages}
                        totalItems={totalItems}
                        onPageChange={handlePageChange}
                    />
                )}
            </main>

            <footer className="glass-footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Watch Japan.</p>
                </div>
            </footer>
        </>
    )
}

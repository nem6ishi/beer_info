import { supabase } from './supabase'
import type { BreweryOption, StyleOption } from '../types/beer'

export const getFlag = (location: string | null): string => {
    if (!location) return '🏳️';
    const loc = location.toLowerCase();

    if (loc.includes('japan')) return '🇯🇵';
    if (loc.includes('united states') || loc.includes('usa') || loc.includes('america')) return '🇺🇸';
    if (loc.includes('canada')) return '🇨🇦';
    if (loc.includes('united kingdom') || loc.includes('uk') || loc.includes('england') || loc.includes('scotland') || loc.includes('wales')) return '🇬🇧';
    if (loc.includes('australia')) return '🇦🇺';
    if (loc.includes('new zealand')) return '🇳🇿';
    if (loc.includes('germany')) return '🇩🇪';
    if (loc.includes('belgium')) return '🇧🇪';
    if (loc.includes('france')) return '🇫🇷';
    if (loc.includes('italy')) return '🇮🇹';
    if (loc.includes('spain')) return '🇪🇸';
    if (loc.includes('netherlands')) return '🇳🇱';
    if (loc.includes('denmark')) return '🇩🇰';
    if (loc.includes('norway')) return '🇳🇴';
    if (loc.includes('sweden')) return '🇸🇪';
    if (loc.includes('poland')) return '🇵🇱';
    if (loc.includes('czech')) return '🇨🇿';
    if (loc.includes('ireland')) return '🇮🇪';
    if (loc.includes('china')) return '🇨🇳';
    if (loc.includes('hong kong')) return '🇭🇰';
    if (loc.includes('taiwan')) return '🇹🇼';
    if (loc.includes('korea')) return '🇰🇷';
    if (loc.includes('mexico')) return '🇲🇽';
    if (loc.includes('brazil')) return '🇧🇷';
    if (loc.includes('estonia')) return '🇪🇪';
    if (loc.includes('latvia')) return '🇱🇻';
    if (loc.includes('lithuania')) return '🇱🇹';

    return '🏳️';
}

export interface AvailableFilters {
    styles: (string | StyleOption)[];
    breweries: BreweryOption[];
}

// In-memory cache for fast repeated lookups (TTL: 5 minutes)
let cachedFilters: AvailableFilters | null = null;
let cachedBreweries: BreweryOption[] | null = null;
let cacheExpiry = 0;
let inFlightFiltersPromise: Promise<AvailableFilters> | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000;

async function fetchBreweriesFromView(): Promise<BreweryOption[]> {
    const breweryMap = new Map<string, { name: string; location: string | null; searchTerms: Set<string> }>();
    const step = 1000;
    let offset = 0;

    while (true) {
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_brewery_name, brewery_location, brewery_name_jp, brewery_name_en')
            .not('untappd_brewery_name', 'is', null)
            .neq('untappd_brewery_name', '')
            .range(offset, offset + step - 1);

        if (error) throw error;
        if (!data || data.length === 0) break;

        data.forEach(item => {
            const name = item.untappd_brewery_name;
            if (!breweryMap.has(name)) {
                breweryMap.set(name, {
                    name: name,
                    location: item.brewery_location,
                    searchTerms: new Set()
                });
            } else if (!breweryMap.get(name)!.location && item.brewery_location) {
                breweryMap.get(name)!.location = item.brewery_location;
            }
            const mapItem = breweryMap.get(name)!;
            if (item.brewery_name_jp) mapItem.searchTerms.add(item.brewery_name_jp);
            if (item.brewery_name_en) mapItem.searchTerms.add(item.brewery_name_en);
        });

        if (data.length < step) break;
        offset += step;
    }

    return Array.from(breweryMap.values())
        .map(b => ({
            name: b.name,
            flag: getFlag(b.location),
            searchStr: Array.from(b.searchTerms).join(' ')
        }))
        .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
}

export async function fetchAvailableFilters(forceRefresh: boolean = false): Promise<AvailableFilters> {
    const now = Date.now();
    if (!forceRefresh && cachedFilters && cacheExpiry > now) {
        return cachedFilters;
    }

    if (!forceRefresh && inFlightFiltersPromise) {
        return inFlightFiltersPromise;
    }

    const loadPromise = (async (): Promise<AvailableFilters> => {
        let rpcStyles: (string | StyleOption)[] = [];

        try {
            // Try RPC first (Migration 014 format: returns { styles, breweries: [{ name, location, searchStr }] })
            const { data: rpcData, error: rpcError } = await supabase.rpc('get_available_filters').single();
            const typedRpcData = rpcData as { styles?: (string | StyleOption)[]; breweries?: any[] } | null;

            if (!rpcError && Array.isArray(typedRpcData?.styles) && typedRpcData.styles.length > 0) {
                rpcStyles = typedRpcData.styles;
            }

            if (!rpcError && typedRpcData?.breweries && Array.isArray(typedRpcData.breweries) && typedRpcData.breweries.length > 0) {
                const first = typedRpcData.breweries[0];
                // Check if returned breweries match the new structure (has 'name')
                if (first && typeof first === 'object' && 'name' in first && first.name) {
                    const breweries: BreweryOption[] = typedRpcData.breweries
                        .map((b: any) => ({
                            name: b.name,
                            flag: getFlag(b.location),
                            searchStr: b.searchStr || ''
                        }))
                        .sort((a: BreweryOption, b: BreweryOption) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));

                    const result: AvailableFilters = { styles: rpcStyles, breweries };
                    cachedFilters = result;
                    cachedBreweries = breweries;
                    cacheExpiry = Date.now() + CACHE_TTL_MS;
                    return result;
                }
            }
        } catch (e) {
            // RPC failed or not supported, continue to fallback
        }

        // Fallback: Paginated fetch from beer_info_view (avoids 1,000 row PostgREST limit)
        // Preserve styles obtained from RPC so the Style filter is never empty on fallback
        const breweries = await fetchBreweriesFromView();
        const result: AvailableFilters = {
            styles: rpcStyles.length > 0 ? rpcStyles : (cachedFilters?.styles || []),
            breweries
        };
        cachedFilters = result;
        cachedBreweries = breweries;
        cacheExpiry = Date.now() + CACHE_TTL_MS;
        return result;
    })();

    inFlightFiltersPromise = loadPromise;
    try {
        return await loadPromise;
    } finally {
        if (inFlightFiltersPromise === loadPromise) {
            inFlightFiltersPromise = null;
        }
    }
}

export async function fetchAvailableBreweries(forceRefresh: boolean = false): Promise<BreweryOption[]> {
    const now = Date.now();
    if (!forceRefresh && cachedBreweries && cacheExpiry > now) {
        return cachedBreweries;
    }
    const filters = await fetchAvailableFilters(forceRefresh);
    return filters.breweries;
}

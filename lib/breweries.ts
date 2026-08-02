import { supabase } from './supabase'

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

export async function fetchAvailableBreweries() {
    const { data, error } = await supabase
        .from('beer_info_view')
        .select('untappd_brewery_name, brewery_location, brewery_name_jp, brewery_name_en')
        .not('untappd_brewery_name', 'is', null)
        .neq('untappd_brewery_name', '')

    if (error) throw error

    const breweryMap = new Map<string, { name: string; location: string | null; searchTerms: Set<string> }>();

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

    const breweries = Array.from(breweryMap.values())
        .map(b => ({
            name: b.name,
            flag: getFlag(b.location),
            searchStr: Array.from(b.searchTerms).join(' ')
        }))
        .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));

    return breweries;
}

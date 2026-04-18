import type { NextApiRequest, NextApiResponse } from 'next'
import { supabase } from '../../lib/supabase'

// Helper to map country to flag
const getFlag = (location: string | null): string => {
    if (!location) return '🏳️'; // Unknown
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

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    try {
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_brewery_name, brewery_location') // Fetch location
            .not('untappd_brewery_name', 'is', null)
            .neq('untappd_brewery_name', '')

        if (error) throw error

        // Deduplicate by name, keeping the one with location if possible
        const breweryMap = new Map<string, { name: string; location: string | null }>();

        data.forEach(item => {
            const name = item.untappd_brewery_name;
            if (!breweryMap.has(name) || (!breweryMap.get(name)!.location && item.brewery_location)) {
                breweryMap.set(name, {
                    name: name,
                    location: item.brewery_location
                });
            }
        });

        const breweries = Array.from(breweryMap.values())
            .map(b => ({
                name: b.name,
                flag: getFlag(b.location)
            }))
            .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));

        res.status(200).json({ breweries })
    } catch (err: any) {
        console.error('Error fetching breweries:', err)
        res.status(500).json({ error: err.message })
    }
}

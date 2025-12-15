import { supabase } from '../../lib/supabase'

export default async function handler(req, res) {
    try {
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_brewery_name')
            .not('untappd_brewery_name', 'is', null)
            .neq('untappd_brewery_name', '')

        if (error) throw error

        // Deduplicate and sort (case-insensitive)
        const breweries = [...new Set(data.map(item => item.untappd_brewery_name))].sort((a, b) =>
            a.toLowerCase().localeCompare(b.toLowerCase())
        )

        res.status(200).json({ breweries })
    } catch (err) {
        console.error('Error fetching breweries:', err)
        res.status(500).json({ error: err.message })
    }
}

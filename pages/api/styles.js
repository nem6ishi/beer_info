import { supabase } from '../../lib/supabase'

export default async function handler(req, res) {
    try {
        // Fetch distinct styles from the beers table
        // distinct() is not directly exposed in simple select(), simpler to use .select() and process or use rpc if needed.
        // But for < 10k items, simple select of styles and distinct in JS is fine, OR use .rpc if we had one.
        // Better: supabase .select('untappd_style') then unique in JS.
        // Even better: use a postgres function, but I can't easily create one.
        // Let's try to just fetch all styles (lightweight string) and unique them.

        // Wait, 'beers' table might have many rows. Fetching all might be slow.
        // Is there a better way? 
        // supabase.from('beers').select('untappd_style', { count: 'exact', head: false }) 
        // effectively getting all.

        // Let's use a simple query.
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_style')
            .not('untappd_style', 'is', null)
            .neq('untappd_style', '')

        if (error) throw error

        // Count occurrences of each style
        const styleCounts = data.reduce((acc, item) => {
            const style = item.untappd_style
            acc[style] = (acc[style] || 0) + 1
            return acc
        }, {})

        // Convert to array and sort by count (descending), then alphabetically
        const styles = Object.entries(styleCounts)
            .map(([style, count]) => ({ style, count }))
            .sort((a, b) => b.count - a.count || a.style.localeCompare(b.style))

        res.status(200).json({ styles })
    } catch (err) {
        console.error('Error fetching styles:', err)
        res.status(500).json({ error: err.message })
    }
}

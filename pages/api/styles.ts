import type { NextApiRequest, NextApiResponse } from 'next'
import { supabase } from '../../lib/supabase'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
    try {
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_style')
            .not('untappd_style', 'is', null)
            .neq('untappd_style', '')

        if (error) throw error

        // Count occurrences of each style
        const styleCounts = (data as { untappd_style: string }[]).reduce((acc: Record<string, number>, item) => {
            const style = item.untappd_style
            acc[style] = (acc[style] || 0) + 1
            return acc
        }, {})

        // Convert to array and sort by count (descending), then alphabetically
        const styles = Object.entries(styleCounts)
            .map(([style, count]) => ({ style, count }))
            .sort((a, b) => b.count - a.count || a.style.localeCompare(b.style))

        res.status(200).json({ styles })
    } catch (err: any) {
        console.error('Error fetching styles:', err)
        res.status(500).json({ error: err.message })
    }
}

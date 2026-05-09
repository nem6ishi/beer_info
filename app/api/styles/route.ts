import { NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'

export async function GET(request: Request) {
    try {
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_style')
            .not('untappd_style', 'is', null)
            .neq('untappd_style', '')

        if (error) throw error

        const styleCounts = (data as { untappd_style: string }[]).reduce((acc: Record<string, number>, item) => {
            const style = item.untappd_style
            acc[style] = (acc[style] || 0) + 1
            return acc
        }, {})

        const styles = Object.entries(styleCounts)
            .map(([style, count]) => ({ style, count }))
            .sort((a, b) => b.count - a.count || a.style.localeCompare(b.style))

        return NextResponse.json({ styles })
    } catch (err: any) {
        console.error('Error fetching styles:', err)
        return NextResponse.json({ error: err.message }, { status: 500 })
    }
}

import { NextResponse } from 'next/server'
import { supabase } from '../../../lib/supabase'

export async function GET(request: Request) {
    try {
        // Try RPC first for fast, accurate full-table aggregation without 1,000 row limits
        const { data: rpcData, error: rpcError } = await supabase.rpc('get_available_filters').single();
        const typedRpcData = rpcData as { styles?: (string | { style: string; count: number })[] } | null;
        if (!rpcError && typedRpcData?.styles && Array.isArray(typedRpcData.styles) && typedRpcData.styles.length > 0) {
            const rawStyles = typedRpcData.styles;
            const styles = rawStyles.map((item: any) => {
                if (typeof item === 'string') return { style: item, count: 0 };
                return { style: item.style || '', count: Number(item.count) || 0 };
            }).filter((s: { style: string }) => s.style);
            return NextResponse.json({ styles });
        }

        // Fallback: direct view query
        const { data, error } = await supabase
            .from('beer_info_view')
            .select('untappd_style')
            .not('untappd_style', 'is', null)
            .neq('untappd_style', '')
            .limit(10000)

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

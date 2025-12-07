import { supabase } from '../../lib/supabase'

export default async function handler(req, res) {
    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' })
    }

    try {
        // Get total beers
        const { count: totalBeers } = await supabase
            .from('beers')
            .select('*', { count: 'exact', head: true })

        // Get beers with Untappd data
        const { count: beersWithUntappd } = await supabase
            .from('beers')
            .select('*', { count: 'exact', head: true })
            .not('untappd_url', 'is', null)

        // Get beers with Gemini data
        const { count: beersWithGemini } = await supabase
            .from('beers')
            .select('*', { count: 'exact', head: true })
            .or('brewery_name_en.not.is.null,brewery_name_jp.not.is.null')

        // Get unique shops
        const { data: shopsData } = await supabase
            .from('beers')
            .select('shop')
            .distinct()

        const shops = shopsData ? shopsData.map(s => s.shop) : []

        // Get last scrape time
        const { data: lastScrapeData } = await supabase
            .from('beers')
            .select('scrape_timestamp')
            .order('scrape_timestamp', { ascending: false })
            .limit(1)

        const lastScrape = lastScrapeData && lastScrapeData.length > 0
            ? lastScrapeData[0].scrape_timestamp
            : null

        return res.status(200).json({
            total_beers: totalBeers || 0,
            total_shops: shops.length,
            beers_with_untappd: beersWithUntappd || 0,
            beers_with_gemini: beersWithGemini || 0,
            last_scrape: lastScrape,
            shops
        })
    } catch (error) {
        console.error('API error:', error)
        return res.status(500).json({ error: 'Internal server error' })
    }
}

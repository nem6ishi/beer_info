import { NextResponse } from 'next/server'
import { fetchAvailableBreweries } from '../../../lib/breweries'

export const revalidate = 300;

export async function GET(request: Request) {
    try {
        const breweries = await fetchAvailableBreweries();
        return NextResponse.json({ breweries })
    } catch (err: any) {
        console.error('Error fetching breweries:', err)
        return NextResponse.json({ error: err.message }, { status: 500 })
    }
}


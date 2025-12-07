export class BeerAPI {
    constructor(url = '/api/beers') {
        this.url = url;
    }

    async fetchBeers(page = 1, limit = 100, search = '', sort = 'newest') {
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: limit.toString(),
                search,
                sort
            });
            const response = await fetch(`${this.url}?${params}`);
            if (!response.ok) throw new Error("Failed to load data");
            const data = await response.json();
            return data; // Returns { beers: [...], pagination: {...} }
        } catch (error) {
            console.error("API Error:", error);
            throw error;
        }
    }
}

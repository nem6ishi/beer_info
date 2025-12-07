export class BeerAPI {
    constructor(url = 'beers.json') {
        this.url = url;
    }

    async fetchBeers() {
        try {
            const response = await fetch(`${this.url}?t=${new Date().getTime()}`);
            if (!response.ok) throw new Error("Failed to load data");
            return await response.json();
        } catch (error) {
            console.error("API Error:", error);
            throw error;
        }
    }
}

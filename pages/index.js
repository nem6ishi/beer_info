import Head from 'next/head'

export default function Home() {
    return (
        <>
            <Head>
                <meta charSet="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>Craft Beer Alert Japan</title>
                <meta name="description" content="Discover premium craft beers collected from the best Japanese shops." />
                <link rel="preconnect" href="https://fonts.googleapis.com" />
                <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
                <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet" />
            </Head>

            <div className="background-globes">
                <div className="globe globe-1"></div>
                <div className="globe globe-2"></div>
            </div>

            <header className="glass-header">
                <div className="container header-content">
                    <h1>Craft Beer Alert Japan</h1>
                    <div className="search-bar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                            strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                        <input type="text" id="searchInput" placeholder="Search beers..."
                            aria-label="Search for beers by name or brewery" />
                    </div>
                </div>
            </header>

            <main className="container">
                <div className="controls-bar">
                    <div className="sort-container">
                        <label htmlFor="sortSelect" className="sort-label">Sort by:</label>
                        <div className="select-wrapper">
                            <select id="sortSelect" className="sort-select">
                                <option value="newest">Newest Arrival</option>
                                <option value="price_asc">Price: Low to High</option>
                                <option value="price_desc">Price: High to Low</option>
                                <option value="abv_desc">ABV: High to Low</option>
                                <option value="rating_desc">Untappd Rating: High to Low</option>
                                <option value="name_asc">Name: A to Z</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div id="statusMessage" className="status-message">Loading collection...</div>
                <div className="table-container">
                    <table className="beer-table">
                        <thead>
                            <tr>
                                <th className="col-img">Image</th>
                                <th className="col-name">Beer Info</th>
                                <th className="col-style">Style / Stats</th>
                                <th className="col-price">Price</th>
                                <th className="col-untappd">Untappd</th>
                                <th className="col-shop">Shop</th>
                                <th className="col-registered">Available Since</th>
                            </tr>
                        </thead>
                        <tbody id="beerTableBody">
                            {/* Rows will be injected here */}
                        </tbody>
                    </table>
                </div>
                <div id="pagination"></div>
            </main>

            <footer className="glass-footer">
                <div className="container">
                    <p>&copy; 2025 Craft Beer Alert Japan. Data sourced from Beervolta &amp; Chouseiya.</p>
                </div>
            </footer>

            <script type="module" src="/app-cloud.js"></script>
        </>
    )
}

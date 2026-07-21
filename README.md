# Craft Beer Watch Japan - Cloud Deployment

This is the cloud-deployed version of the Craft Beer Watch Japan service, using:
- **Vercel** for frontend and API hosting
- **Supabase** for PostgreSQL database
- **GitHub Actions** for automated scraping and enrichment

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ (for local development)
- Python 3.11+ (for scraping/enrichment)
- GitHub account
- Supabase account (free tier)
- Vercel account (free tier)

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd beer_info
   ```

2. **Set up Supabase**
   - Create a new project at [supabase.com](https://supabase.com)
   - Run the SQL schema in `supabase_schema.sql` in the SQL Editor
   - Get your project URL and keys from Settings > API

3. **Set up environment variables**
   ```bash
   cp .env.example .env.local
   ```
   
   Fill in your Supabase credentials:
   - `NEXT_PUBLIC_SUPABASE_URL`: Your Supabase project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`: Your anon/public key
   - `SUPABASE_SERVICE_KEY`: Your service_role key (for scripts)
   - `GEMINI_API_KEY`: Your Google Gemini API key

4. **Install dependencies**
   ```bash
   # Node.js (for frontend/API)
   npm install
   
   # Python (for scraping/enrichment)
   # We use uv for dependency management
   uv sync
   ```

5. **Run locally**
   ```bash
   npm run dev
   ```
   
   Visit http://localhost:3000

## 📦 Deployment

### Deploy to Vercel

1. **Connect your GitHub repository** to Vercel

2. **Configure environment variables** in Vercel dashboard:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

3. **Deploy**
   ```bash
   vercel --prod
   ```

### Configure GitHub Actions

1. **Add secrets** to your GitHub repository (Settings > Secrets):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `GEMINI_API_KEY`

2. **Enable GitHub Actions** in your repository settings

3. **Workflows will run automatically**:
   - **Scraping**: Every hour (triggers Gemini enrichment on completion)
   - **Gemini Enrichment**: After scraping + 4x daily (0:00, 6:00, 12:00, 18:00 JST)
   - **Untappd Enrichment**: After Gemini enrichment + 2x daily (0:30, 12:30 JST)

## 🛠️ Development

### CLI Usage

We use a central CLI for all management tasks.

```bash
# 1. Scrape to Supabase (fetch from all shops)
uv run python cli.py scrape --limit 100 --new

# 2. Extract Beer Info via LLM (Gemini / Local MLX)
uv run python cli.py enrich-extract --limit 50

# 3. Enrich with Untappd (search based on extracted info)
uv run python cli.py enrich-untappd --limit 50 --mode missing

# 4. Enrich Breweries (update brewery details from Untappd)
uv run python cli.py enrich-breweries --limit 50

# [Bonus] Run full enrichment pipeline (Extract -> Untappd -> Breweries)
uv run python cli.py enrich --limit 50

# [Bonus] Clean corrupted data safely (defaults to dry-run)
uv run python cli.py clean --table scraped_beers --column name --pattern '%%'
```

### Project Structure

```
/
├── .github/workflows/      # GitHub Actions
├── app/                    # Next.js App Router pages & API routes
├── backend/                # Python Backend
│   ├── src/
│   │   ├── commands/       # Command logic (Scrape, Enrich)
│   │   ├── core/           # Config, DB, Logging
│   │   ├── scrapers/       # Site scrapers
│   │   └── services/       # Service modules (Gemini, Untappd)
│   ├── tests/              # Python tests
│   └── scripts/            # Utility scripts
├── components/             # React components
├── database/               # Database schema & migrations
├── docs/                   # Documentation
├── hooks/                  # React custom hooks
├── lib/                    # Shared Next.js utilities
├── public/                 # Static assets
├── styles/                 # CSS stylesheets
├── types/                  # TypeScript type definitions
└── cli.py                  # CLI Entry Point
```

## 📊 API Endpoints

- `GET /api/beers?search=&sort=newest&page=1&limit=100` - Get beers with filtering

## 🔄 Data Flow

1. **Scraping**: `backend/src/commands/scrape.py` fetches data from shops and upserts to `scraped_beers`.
2. **Enrichment (Gemini)**: `backend/src/commands/enrich_gemini.py` reads `scraped_beers` AND uses Gemini API to extract metadata, saving to `gemini_data`.
3. **Enrichment (Untappd)**: `backend/src/commands/enrich_untappd.py` reads valid metadata and searches Untappd, saving to `untappd_data`.
4. **Integration**: `beer_info_view` in Supabase joins these 3 tables to provide a unified "beers" view.
5. **Frontend**: Next.js API (`/api/beers`) queries `beer_info_view` to serve the UI.

## 📝 License

MIT

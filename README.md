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

4 **Migrate existing data** (one-time)
   ```bash
   pip install supabase
   export SUPABASE_URL="your-url"
   export SUPABASE_SERVICE_KEY="your-service-key"
   python scripts/migrate_to_supabase.py
   ```

5. **Install dependencies**
   ```bash
   # Node.js (for frontend/API)
   npm install
   
   # Python (for scraping/enrichment)
   pip install -r requirements.txt
   ```

6. **Run locally**
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
   - Scraping: Every 2 hours
   - Enrichment: Every 6 hours

You can also trigger workflows manually from the Actions tab.

## 🛠️ Development

### Local CLI (for testing)

```bash
# Scrape to Supabase
python scripts/scrape_to_supabase.py

# Enrich data in Supabase
python scripts/enrich_supabase.py --limit 50

# Original local-file based CLI (deprecated)
python -m app.cli serve
python -m app.cli scrape
python -m app.cli enrich
```

### Project Structure

```
/
├── .github/workflows/    # GitHub Actions
│   ├── scrape.yml        # Scheduled scraping
│   └── enrich.yml        # Scheduled enrichment
├── app/                  # Python backend logic
│   ├── scrapers/         # Site scrapers
│   └── services/         # Business logic
├── lib/                  # Next.js utilities
│   └── supabase.js       # Supabase client
├── pages/                # Next.js pages
│   ├── index.js          # Frontend
│   └── api/              # API routes
├── public/               # Static assets
├── scripts/              # Utility scripts
│   ├── migrate_to_supabase.py
│   ├── scrape_to_supabase.py
│   └── enrich_supabase.py
├── supabase_schema.sql   # Database schema
└── vercel.json           # Vercel config
```

## 📊 API Endpoints

- `GET /api/beers?search=&sort=newest&page=1&limit=100` - Get beers with filtering
- `GET /api/stats` - Get database statistics

## 🔄 Data Flow

1. **GitHub Actions** runs scrapers every 2 hours
2. **Scrapers** fetch data from Japanese beer shops
3. **Data** is written to **Supabase** PostgreSQL
4. **Enrichment** runs every 6 hours (Gemini + Untappd)
5. **Frontend** fetches data from **Vercel API routes**
6. **API routes** query **Supabase** and return JSON

## 📝 License

MIT

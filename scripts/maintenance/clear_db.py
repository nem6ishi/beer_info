import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Clear scraped_beers table (New Schema)
print("Clearing 'scraped_beers' table...")
try:
    # Delete all rows in scraped_beers
    supabase.table('scraped_beers').delete().neq('url', 'placeholder').execute()
    print("✅ 'scraped_beers' table cleared.")
except Exception as e:
    print(f"⚠️ Error clearing 'scraped_beers': {e}")

# Optional: Clear old 'beers' table if it still exists and gets in the way
# print("Clearing old 'beers' table...")
# supabase.table('beers').delete().neq('url', 'placeholder').execute()

print("✨ Database scrape data cleared.")

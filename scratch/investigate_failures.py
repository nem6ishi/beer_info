import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def get_failures():
    # Fetch beers with no proper untappd link or marked as failures
    # We'll check scraped_beers first
    res = supabase.table("scraped_beers") \
        .select("name, shop, untappd_url") \
        .or_("untappd_url.is.null,untappd_url.ilike.%/search?%") \
        .limit(10) \
        .execute()
    
    for row in res.data:
        print(f"Shop: {row['shop']} | Name: {row['name']} | URL: {row['untappd_url']}")

if __name__ == "__main__":
    get_failures()

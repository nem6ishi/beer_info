
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

name_query = "SUNSHINE SUPERSTAR"
response = supabase.table("beer_info_view").select("name, first_seen, brewery_name_en, url").ilike("name", f"%{name_query}%").execute()

print(f"Checking status for: {name_query}")
for beer in response.data:
    print(f"- {beer['name'][:50]}... | {beer['first_seen']} | Enriched: {bool(beer['brewery_name_en'])}")

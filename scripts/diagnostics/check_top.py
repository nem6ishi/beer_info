
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

response = supabase.table("beer_info_view").select("name, first_seen, shop, brewery_name_en").order("first_seen", desc=True).limit(5).execute()

print("Top 5 Beers on Web Page & Enrichment Status:")
for i, beer in enumerate(response.data, 1):
    is_enriched = bool(beer.get('brewery_name_en'))
    status = "✅ Done" if is_enriched else "⏳ Pending (Next)"
    print(f"{i}. {beer['name'][:40]}... | {status}")

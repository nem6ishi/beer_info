
import asyncio
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

name_query = "SUNSHINE SUPERSTAR"
# Get the URL of the top item (Newest)
response = supabase.table("beer_info_view").select("url, name").ilike("name", f"%{name_query}%").order("first_seen", desc=True).limit(1).execute()

if response.data:
    target_url = response.data[0]['url']
    print(f"Clearing Gemini data for: {response.data[0]['name']}")
    
    # Delete from gemini_data using the URL
    # Note: gemini_data primary key is 'url'
    res = supabase.table("gemini_data").delete().eq("url", target_url).execute()
    print("Deleted.")
else:
    print("Target beer not found.")

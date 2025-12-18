
import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials not found in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def clear_arome():
    print("🗑️ Clearing Arome data from scraped_beers...")
    
    # Delete from scraped_beers where shop is 'Arome'
    response = supabase.table("scraped_beers").delete().eq("shop", "Arome").execute()
    
    # Supabase delete response usually contains 'data' with the deleted rows
    deleted_count = len(response.data) if response.data else 0
    print(f"✅ Deleted {deleted_count} items from Arome.")

if __name__ == "__main__":
    asyncio.run(clear_arome())

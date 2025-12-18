from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

links = [
    {
        "product_url": "https://www.arome.jp/products/detail.php?product_id=6737",
        "untappd_url": "https://untappd.com/b/messorem-aussi-green-plus-de-hops-aussi-cher/6499796"
    },
    {
        "product_url": "https://www.arome.jp/products/detail.php?product_id=6736",
        "untappd_url": "https://untappd.com/b/vertere-emoryi/6043841"
    }
]

for link in links:
    p_url = link["product_url"]
    u_url = link["untappd_url"]
    print(f"🔗 Linking {p_url} to {u_url}...")

    # 1. Update gemini_data (persistence)
    supabase.table("gemini_data").update({"untappd_url": u_url}).eq("url", p_url).execute()

    # 2. Update scraped_beers (view link)
    supabase.table("scraped_beers").update({"untappd_url": u_url}).eq("url", p_url).execute()

print("✅ All Linked!")

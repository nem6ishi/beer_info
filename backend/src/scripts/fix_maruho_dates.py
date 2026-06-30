import asyncio
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List
from backend.src.core.db import get_supabase_client
from dateutil import parser as date_parser

BASE_URL = "https://maruho.shop"

async def fetch_all_maruho_timestamps() -> Dict[str, str]:
    """
    Shopify API から全商品の URL と published_at (または created_at) を取得する
    """
    url_to_date: Dict[str, str] = {}
    page = 1
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            api_url = f"{BASE_URL}/products.json?limit=250&page={page}"
            print(f"Fetching {api_url}...")
            try:
                resp = await client.get(api_url)
                if resp.status_code != 200:
                    break
                data = resp.json()
                products = data.get("products", [])
                if not products:
                    break
                
                for prod in products:
                    handle = prod.get("handle")
                    if not handle:
                        continue
                    url = f"{BASE_URL}/products/{handle}"
                    raw_date = prod.get("published_at") or prod.get("created_at")
                    if raw_date:
                        try:
                            dt = date_parser.parse(raw_date)
                            dt_utc = dt.astimezone(timezone.utc)
                            url_to_date[url] = dt_utc.isoformat()
                        except Exception:
                            pass
                
                page += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break

    print(f"Total extracted timestamp mappings: {len(url_to_date)}")
    return url_to_date

async def update_record(client: Any, url: str, first_seen_iso: str, sem: asyncio.Semaphore) -> None:
    async with sem:
        try:
            # 1件ずつ update して他のカラムを保持
            client.table("scraped_beers").update({"first_seen": first_seen_iso}).eq("url", url).execute()
        except Exception as e:
            print(f"Failed to update {url}: {e}")

async def main() -> None:
    print("🚀 Starting Maruho date correction script...")
    url_to_date = await fetch_all_maruho_timestamps()
    if not url_to_date:
        print("❌ No products fetched.")
        return

    client = get_supabase_client()
    sem = asyncio.Semaphore(20)  # 並列度20で負荷を調整

    tasks = [
        update_record(client, url, iso_date, sem)
        for url, iso_date in url_to_date.items()
    ]
    
    print(f"⏳ Updating {len(tasks)} records in Supabase...")
    await asyncio.gather(*tasks)
    print("✨ All Maruho records have been updated with their actual published dates!")

if __name__ == "__main__":
    asyncio.run(main())

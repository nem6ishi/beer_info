import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.db import get_supabase_client
from app.scrapers import arome

async def fix_arome_top_20():
    print("🚀 Starting Arome Top 20 Fix (Step 2 Only)...")
    supabase = get_supabase_client()
    
    # We assume Step 1 (Full Scrape & Past Timestamp) is DONE.
    # Now we just need to bring the Top 20 to NOW.
    
    # Scrape only Page 1 (Limit 20 is enough)
    print("\n📦 Scraping Top 20 items from Arome...")
    try:
        # Limit 20
        items = await arome.scrape_arome(limit=20) 
    except Exception as e:
        print(f"❌ Error scraping Arome: {e}")
        return

    if not items:
        print("⚠️ No items scaped from Arome.")
        return
        
    print(f"✅ Scraped {len(items)} items.")
    
    current_time = datetime.now(timezone.utc)
    
    updates = []
    for i, item in enumerate(items):
        # We want these to be the MOST recent.
        # Order index: 0 is newest. 
        # timestamp = Now - (index * 1 second)
        ts = current_time - timedelta(seconds=i)
        
        # KEY FIX: Include ALL fields to satisfy upsert constraints
        # Or better: Use the full item dict from scraper and just update timestamps
        update_item = item.copy()
        update_item['first_seen'] = ts.isoformat()
        update_item['last_seen'] = current_time.isoformat()
        update_item['shop'] = "アローム" # Ensure consistent shop name
        
        updates.append(update_item)
        
    print(f"💾 Upserting {len(updates)} items with CURRENT timestamps...")
    try:
        # Upsert with full data
        supabase.table('scraped_beers').upsert(updates, on_conflict='url').execute()
        print("  ✅ Top 20 updated successfully.")
    except Exception as e:
        print(f"  ❌ Error updating top 20: {e}")

    print("\n🏁 Done!")

if __name__ == "__main__":
    asyncio.run(fix_arome_top_20())

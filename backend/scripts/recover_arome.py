import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.scrapers import arome
from backend.src.core.db import get_supabase_client
from backend.src.commands.scrape import run_and_save_store

async def main():
    print("Starting Arome recovery scrape (with 60min timeout)...")
    sb = get_supabase_client()
    base_time = datetime.now(timezone.utc)
    
    # タイムアウトを 3600秒(60分) にして実行
    new_c, upd_c, total = await run_and_save_store(
        arome.scrape_arome(full_scrape=True),
        'Arôme',
        sb,
        {},  # existing_data
        False, # new_only
        False, # reset_first_seen
        base_time,
        3, # store_index
        timeout=3600
    )
    print(f"Finished. New: {new_c}, Updated: {upd_c}, Total: {total}")

if __name__ == "__main__":
    asyncio.run(main())

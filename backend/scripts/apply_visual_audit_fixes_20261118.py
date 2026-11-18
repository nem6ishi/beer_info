"""
Full visual audit fix script for 2026-11-18.
Applies subagent-verified corrections from final_action_plan.json to Supabase:
  1. Scrapes and upserts missing untappd_data for UPDATE_URL & SCRAPE_CURRENT_URL targets
  2. Updates scraped_beers & gemini_data for UPDATE_URL
  3. Marks SET products (is_set=True, product_type='set', untappd_url=None)
  4. Marks NON-BEER products (product_type='other', untappd_url=None)
  5. Unlinks clearly misassigned beers with no valid match (untappd_url=None)
  6. Refreshes materialized view beer_info_view
"""
import argparse
import asyncio
import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from backend.src.core.db import get_supabase_client, refresh_materialized_view, sync_execute
from backend.src.core.utils import map_details_to_payload
from backend.src.services.untappd.http_client import close_async_client, scrape_beer_details

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_PLAN_PATH = (
    "/Users/nemu/.gemini/antigravity/brain/ca005f3d-9706-41a0-8df9-fb41a072b534/scratch/final_action_plan.json"
)


def run_db_op(op_func, max_retries=3, delay=1.0):
    for attempt in range(max_retries):
        try:
            return op_func()
        except Exception as e:
            logger.warning(f"DB operation failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(delay * (attempt + 1))


async def apply_fixes(plan_path: Path, execute: bool = False):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    counts = Counter(item["action"] for item in plan)

    logger.info("=== Visual Audit Fix Summary ===")
    for action, cnt in sorted(counts.items()):
        logger.info(f"  {action:20s}: {cnt}")

    if not execute:
        logger.info("\n[DRY-RUN] Sample items per action:")
        for action in ("UPDATE_URL", "SCRAPE_CURRENT_URL", "MARK_SET", "MARK_NON_BEER", "UNLINK"):
            samples = [x for x in plan if x["action"] == action][:5]
            if samples:
                logger.info(f"\n--- {action} (showing {len(samples)} of {counts[action]}) ---")
                for s in samples:
                    logger.info(f"  {s['id']} [{s['stock_status']}][{s['shop']}] {s['name']}")
                    logger.info(f"     Current: {s['current_untappd_url']} -> New: {s['new_untappd_url'] or '(None)'}")
        logger.info("\nRun with --execute to apply changes to Supabase.")
        return

    sb = get_supabase_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Gather unique Untappd URLs needed for UPDATE_URL & SCRAPE_CURRENT_URL
    update_items = [x for x in plan if x["action"] == "UPDATE_URL"]
    scrape_cur_items = [x for x in plan if x["action"] == "SCRAPE_CURRENT_URL"]

    needed_urls = list({x["new_untappd_url"] for x in update_items + scrape_cur_items if x.get("new_untappd_url")})
    logger.info(f"\n[1] Checking {len(needed_urls)} unique Untappd URLs in untappd_data...")

    existing_complete = set()
    for i in range(0, len(needed_urls), 100):
        batch = needed_urls[i : i + 100]
        res = run_db_op(lambda: sync_execute(
            sb.table("untappd_data").select("untappd_url, beer_name, brewery_name").in_("untappd_url", batch)
        ))
        for row in (res.data or []):
            if row.get("beer_name") and row.get("brewery_name"):
                existing_complete.add(row["untappd_url"])

    to_scrape = [u for u in needed_urls if u not in existing_complete]
    logger.info(f"  Already complete in untappd_data: {len(existing_complete)}, Need scraping: {len(to_scrape)}")

    sem = asyncio.Semaphore(5)
    valid_urls = set(existing_complete)
    scraped_ok = 0
    scraped_fail = 0

    async def scrape_and_upsert(u_url: str):
        nonlocal scraped_ok, scraped_fail
        async with sem:
            details = await scrape_beer_details(u_url)
            await asyncio.sleep(0.3)
        if details and details.get("untappd_beer_name"):
            payload = map_details_to_payload(details)
            payload["untappd_url"] = u_url
            payload["fetched_at"] = now_iso
            run_db_op(lambda: sync_execute(sb.table("untappd_data").upsert(payload, on_conflict="untappd_url")))
            valid_urls.add(u_url)
            scraped_ok += 1
        else:
            logger.warning(f"  ❌ Failed to scrape details for {u_url}")
            scraped_fail += 1

    if to_scrape:
        await asyncio.gather(*(scrape_and_upsert(u) for u in to_scrape))
    await close_async_client()
    logger.info(f"  Scraping complete: {scraped_ok} succeeded, {scraped_fail} failed.")

    # 2. Fetch existing gemini_data URLs so we only update/upsert cleanly
    all_target_urls = [x["url"] for x in plan if x["action"] != "KEEP_CURRENT"]
    existing_gemini = set()
    for i in range(0, len(all_target_urls), 100):
        batch = all_target_urls[i : i + 100]
        res = run_db_op(lambda: sync_execute(sb.table("gemini_data").select("url").in_("url", batch)))
        for row in (res.data or []):
            existing_gemini.add(row["url"])

    # 3. Apply UPDATE_URL
    logger.info(f"\n[2] Applying UPDATE_URL ({len(update_items)} items)...")
    updated_count = 0
    skipped_scrape_fail = 0
    for item in update_items:
        p_url = item["url"]
        new_u_url = item["new_untappd_url"]
        if new_u_url not in valid_urls:
            skipped_scrape_fail += 1
            continue
        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": new_u_url,
            "untappd_enriched_at": now_iso,
        }).eq("url", p_url)))
        if p_url in existing_gemini:
            run_db_op(lambda: sync_execute(sb.table("gemini_data").update({
                "untappd_url": new_u_url,
                "updated_at": now_iso,
            }).eq("url", p_url)))
        updated_count += 1
    logger.info(f"  ✅ Updated {updated_count} items (skipped {skipped_scrape_fail} due to scrape failure).")

    # 4. Apply MARK_SET
    set_items = [x for x in plan if x["action"] == "MARK_SET"]
    logger.info(f"\n[3] Applying MARK_SET ({len(set_items)} items)...")
    for item in set_items:
        p_url = item["url"]
        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": None,
            "untappd_enriched_at": now_iso,
        }).eq("url", p_url)))
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert({
            "url": p_url,
            "is_set": True,
            "product_type": "set",
            "untappd_url": None,
            "updated_at": now_iso,
        }, on_conflict="url")))
    logger.info(f"  ✅ Marked {len(set_items)} items as set products.")

    # 5. Apply MARK_NON_BEER
    non_beer_items = [x for x in plan if x["action"] == "MARK_NON_BEER"]
    logger.info(f"\n[4] Applying MARK_NON_BEER ({len(non_beer_items)} items)...")
    for item in non_beer_items:
        p_url = item["url"]
        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": None,
            "untappd_enriched_at": now_iso,
        }).eq("url", p_url)))
        run_db_op(lambda: sync_execute(sb.table("gemini_data").upsert({
            "url": p_url,
            "product_type": "other",
            "untappd_url": None,
            "updated_at": now_iso,
        }, on_conflict="url")))
    logger.info(f"  ✅ Marked {len(non_beer_items)} items as non-beer ('other').")

    # 6. Apply UNLINK
    unlink_items = [x for x in plan if x["action"] == "UNLINK"]
    logger.info(f"\n[5] Applying UNLINK ({len(unlink_items)} items)...")
    for item in unlink_items:
        p_url = item["url"]
        run_db_op(lambda: sync_execute(sb.table("scraped_beers").update({
            "untappd_url": None,
            "untappd_enriched_at": now_iso,
        }).eq("url", p_url)))
        if p_url in existing_gemini:
            run_db_op(lambda: sync_execute(sb.table("gemini_data").update({
                "untappd_url": None,
                "updated_at": now_iso,
            }).eq("url", p_url)))
    logger.info(f"  ✅ Unlinked {len(unlink_items)} misassigned items.")

    # 7. Refresh materialized view
    logger.info("\n[6] Refreshing Materialized View (beer_info_view)...")
    run_db_op(lambda: refresh_materialized_view(sb, logger))
    logger.info("✅ Materialized view refreshed successfully!")


def main():
    parser = argparse.ArgumentParser(description="Apply visual audit fixes to Supabase")
    parser.add_argument("--plan", default=DEFAULT_PLAN_PATH, help="Path to final_action_plan.json")
    parser.add_argument("--execute", action="store_true", help="Actually execute DB updates (default: dry-run)")
    args = parser.parse_args()

    asyncio.run(apply_fixes(Path(args.plan), execute=args.execute))


if __name__ == "__main__":
    main()

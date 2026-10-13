"""
Database Optimization & Storage Cleanup Utility.

Safely cleans up stale/resolved logs to keep the Supabase database within
the free tier limit (500 MB).
"""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.core.logging import setup_logging

logger = logging.getLogger("optimize_storage")


def chunk_list(items: list, size: int):
    """Yield successive chunks from items."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def optimize_storage(
    clean_resolved_failures: bool = True,
    clean_stale_failures_days: Optional[int] = 90,
    clean_gemini_payloads: bool = False,
    dry_run: bool = True,
    batch_size: int = 100,
) -> None:
    """
    Optimizes database storage by cleaning up resolved/stale records.
    """
    logger.info("=" * 70)
    logger.info("🧹 Supabase Storage Optimizer")
    logger.info(f"Mode: {'[DRY RUN - No changes will be made]' if dry_run else '[EXECUTE - Deleting data]'}")
    logger.info("=" * 70)

    client = get_supabase_client()

    # 1. untappd_search_failures: Clean resolved failures
    if clean_resolved_failures:
        logger.info("\n🔍 Checking for resolved failures in untappd_search_failures...")
        res = client.table("untappd_search_failures").select("id", count="exact", head=True).eq("resolved", True).execute()
        resolved_count = res.count or 0
        logger.info(f"  Found {resolved_count} resolved failure records.")

        if resolved_count > 0:
            if dry_run:
                logger.info(f"  [DRY RUN] Would delete {resolved_count} resolved records from untappd_search_failures.")
            else:
                logger.info(f"  🚨 Deleting {resolved_count} resolved records in batches of {batch_size}...")
                deleted_total = 0
                while True:
                    # Fetch batch of IDs to delete
                    batch_res = client.table("untappd_search_failures").select("id").eq("resolved", True).limit(batch_size).execute()
                    ids_to_delete = [r["id"] for r in batch_res.data]
                    if not ids_to_delete:
                        break

                    client.table("untappd_search_failures").delete().in_("id", ids_to_delete).execute()
                    deleted_total += len(ids_to_delete)
                    logger.info(f"    Progress: {deleted_total} / {resolved_count} deleted...")

                logger.info(f"  ✅ Completed: {deleted_total} resolved records deleted.")

    # 2. untappd_search_failures: Clean stale unresolved failures (e.g., > 90 days old)
    if clean_stale_failures_days and clean_stale_failures_days > 0:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=clean_stale_failures_days)).isoformat()
        logger.info(f"\n🔍 Checking for stale unresolved failures older than {clean_stale_failures_days} days (before {cutoff})...")
        res_stale = (
            client.table("untappd_search_failures")
            .select("id", count="exact", head=True)
            .eq("resolved", False)
            .lt("last_failed_at", cutoff)
            .execute()
        )
        stale_count = res_stale.count or 0
        logger.info(f"  Found {stale_count} stale unresolved failure records.")

        if stale_count > 0:
            if dry_run:
                logger.info(f"  [DRY RUN] Would delete {stale_count} stale failure records.")
            else:
                logger.info(f"  🚨 Deleting {stale_count} stale failure records in batches of {batch_size}...")
                deleted_stale = 0
                while True:
                    batch_res = (
                        client.table("untappd_search_failures")
                        .select("id")
                        .eq("resolved", False)
                        .lt("last_failed_at", cutoff)
                        .limit(batch_size)
                        .execute()
                    )
                    ids_to_delete = [r["id"] for r in batch_res.data]
                    if not ids_to_delete:
                        break

                    client.table("untappd_search_failures").delete().in_("id", ids_to_delete).execute()
                    deleted_stale += len(ids_to_delete)
                    logger.info(f"    Progress: {deleted_stale} / {stale_count} deleted...")

                logger.info(f"  ✅ Completed: {deleted_stale} stale failure records deleted.")

    # 3. gemini_data: Clean debug payloads if requested
    if clean_gemini_payloads:
        logger.info("\n🔍 Checking for non-null payloads in gemini_data...")
        res_payloads = client.table("gemini_data").select("url", count="exact", head=True).not_.is_("payload", "null").execute()
        payload_count = res_payloads.count or 0
        logger.info(f"  Found {payload_count} records with debug payloads in gemini_data.")

        if payload_count > 0:
            if dry_run:
                logger.info(f"  [DRY RUN] Would nullify {payload_count} payloads in gemini_data.")
            else:
                logger.info(f"  🚨 Nullifying payloads in batches of {batch_size}...")
                updated_total = 0
                while True:
                    batch_res = client.table("gemini_data").select("url").not_.is_("payload", "null").limit(batch_size).execute()
                    urls_to_update = [r["url"] for r in batch_res.data]
                    if not urls_to_update:
                        break

                    client.table("gemini_data").update({"payload": None}).in_("url", urls_to_update).execute()
                    updated_total += len(urls_to_update)
                    logger.info(f"    Progress: {updated_total} / {payload_count} payloads cleared...")

                logger.info(f"  ✅ Completed: {updated_total} payloads cleared.")

    # 4. Summary & Materialized View Refresh
    if not dry_run:
        logger.info("\n🔄 Refreshing materialized view (beer_info_view)...")
        try:
            refresh_materialized_view(client, logger)
            logger.info("✅ Materialized view refreshed successfully.")
        except Exception as e:
            logger.warning(f"⚠️ Could not refresh materialized view: {e}")

    logger.info("\n✨ Database optimization finished.")


def main():
    setup_logging("optimize_storage")
    parser = argparse.ArgumentParser(description="Optimize Supabase storage by cleaning up stale data")
    parser.add_argument("--execute", action="store_true", help="Actually execute the cleanup (defaults to dry-run)")
    parser.add_argument("--skip-resolved", action="store_true", help="Skip cleaning resolved failures")
    parser.add_argument("--stale-days", type=int, default=90, help="Days threshold for stale unresolved failures (0 to disable)")
    parser.add_argument("--clean-payloads", action="store_true", help="Nullify debug payloads in gemini_data")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for deletions/updates")

    args = parser.parse_args()

    asyncio.run(
        optimize_storage(
            clean_resolved_failures=not args.skip_resolved,
            clean_stale_failures_days=args.stale_days if args.stale_days > 0 else None,
            clean_gemini_payloads=args.clean_payloads,
            dry_run=not args.execute,
            batch_size=args.batch_size,
        )
    )


if __name__ == "__main__":
    main()

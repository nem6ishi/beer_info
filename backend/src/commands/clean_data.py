"""
Command to safely clean corrupted or specific data from the database.
Always defaults to dry-run mode to prevent accidental data loss.
"""
import asyncio
import logging
from typing import Any

from ..core.db import get_supabase_client, sync_execute

logger = logging.getLogger(__name__)

async def clean_data(
    table: str,
    column: str,
    pattern: str,
    dry_run: bool = True
) -> None:
    """
    Safely deletes records from a table matching a LIKE pattern.
    Requires dry_run=False to actually delete data.
    """
    if not table or not column or not pattern:
        logger.error("❌ Table, column, and pattern must be provided.")
        return

    logger.info("=" * 70)
    logger.info(f"🧹 Safe Clean Data Utility")
    logger.info("=" * 70)

    try:
        supabase = get_supabase_client()
        
        # 1. First, always SELECT to show what would be deleted
        logger.info(f"🔍 Checking '{table}' for {column} LIKE '{pattern}'...")
        query = supabase.table(table).select('*').like(column, pattern)
        res: Any = sync_execute(query)
        
        records = res.data or []
        count = len(records)
        
        if count == 0:
            logger.info("✨ No records found matching the criteria. Exiting.")
            return

        logger.warning(f"⚠️  Found {count} records matching the criteria.")
        
        # Show sample of records
        sample_size = min(5, count)
        logger.info(f"\n📋 Sample of records to be deleted ({sample_size} of {count}):")
        for i, rec in enumerate(records[:sample_size]):
            # print first 100 chars of the target column to avoid console spam
            col_val = str(rec.get(column, ''))[:100]
            logger.info(f"  - [{i+1}] ID: {rec.get('id', 'N/A')} | {column}: {col_val}")
            
        if dry_run:
            logger.info("\n🛡️  DRY RUN MODE ENABLED 🛡️")
            logger.info("No data was actually deleted.")
            logger.info("To actually delete these records, run the command with the --execute flag.")
        else:
            logger.critical("\n🚨 EXECUTE MODE: DELETING DATA... 🚨")
            delete_query = supabase.table(table).delete().like(column, pattern)
            del_res = sync_execute(delete_query)
            logger.info(f"✅ Successfully deleted {len(del_res.data)} records from {table}.")
            
    except Exception as e:
        logger.error(f"❌ Error during clean operation: {e}")

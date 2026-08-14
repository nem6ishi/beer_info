"""
Continuous Local LLM Enrichment Loop for Long-running Unattended Processing.

This script runs batch enrichment in a loop until all remaining beers are processed.
Designed to run safely during long absences (e.g. 5 days).
"""
import sys
import os
import time
import argparse
import logging
import subprocess
from datetime import datetime

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("local_enrich_loop.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("local_enrich_loop")

def get_remaining_count() -> int:
    """Fetch count of items in beer_info_view needing enrichment."""
    try:
        from backend.src.core.db import get_supabase_client
        supabase = get_supabase_client()
        res = supabase.table('beer_info_view').select('url', count='exact').or_('brewery_name_en.is.null,untappd_url.is.null,untappd_url.ilike.%/search?%').execute()
        return res.count or 0
    except Exception as e:
        logger.error(f"Failed to fetch remaining count: {e}")
        return -1

def run_loop(batch_size: int = 50, llm_provider: str = "local_mlx", mode: str = "extract", sleep_between: int = 5):
    logger.info("==================================================")
    logger.info(f"🚀 Starting Local Enrichment Loop (LLM: {llm_provider}, Mode: {mode})")
    logger.info("==================================================")

    processed_batches = 0
    consecutive_errors = 0

    while True:
        remaining = get_remaining_count()
        logger.info(f"📊 Progress Status: ~{remaining} items remaining needing enrichment")

        if remaining == 0:
            logger.info("🎉 All items have been processed! Loop finished.")
            break

        command_name = "enrich-extract" if mode == "extract" else "enrich"
        cmd = [
            "uv", "run", "python", "-m", "backend.src.cli",
            command_name,
            "--llm", llm_provider,
            "--limit", str(batch_size)
        ]

        start_time = datetime.now()
        logger.info(f"▶️ Executing batch #{processed_batches + 1} (Limit: {batch_size})...")

        try:
            res = subprocess.run(cmd, check=False)
            if res.returncode == 0:
                consecutive_errors = 0
                processed_batches += 1
                logger.info(f"✅ Batch #{processed_batches} completed successfully in {datetime.now() - start_time}.")
            else:
                consecutive_errors += 1
                logger.error(f"⚠️ Batch exited with code {res.returncode}. Consecutive errors: {consecutive_errors}")

        except Exception as e:
            consecutive_errors += 1
            logger.error(f"❌ Exception running batch: {e}. Consecutive errors: {consecutive_errors}")

        if consecutive_errors >= 10:
            logger.critical("🛑 Too many consecutive errors (10). Pausing loop for 5 minutes before retrying...")
            time.sleep(300)
            consecutive_errors = 0
        else:
            time.sleep(sleep_between)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Continuous Local LLM Enrichment Loop")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of items per batch (default: 50)")
    parser.add_argument("--llm", type=str, default="local_mlx", help="LLM provider (default: local_mlx)")
    parser.add_argument("--mode", type=str, choices=["extract", "full"], default="extract", help="Mode: 'extract' (LLM only) or 'full' (LLM + Untappd)")
    parser.add_argument("--sleep", type=int, default=5, help="Sleep seconds between batches (default: 5)")
    args = parser.parse_args()

    run_loop(batch_size=args.batch_size, llm_provider=args.llm, mode=args.mode, sleep_between=args.sleep)

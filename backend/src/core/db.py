# backend/src/core/db.py
import asyncio
from typing import Optional, Any
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings
import logging

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
             raise ValueError("Supabase credentials not set in environment or .env")
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase_client

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
def sync_execute(query_builder: Any) -> Any:
    """Supabase クエリビルダーをリトライ付きで同期実行する。"""
    return query_builder.execute()

async def async_execute(query_builder: Any) -> Any:
    """
    Supabase クエリビルダーを asyncio.to_thread かつリトライ付きで非同期実行する。
    イベントループのブロッキングを防ぎます。
    """
    return await asyncio.to_thread(sync_execute, query_builder)

def refresh_materialized_view(supabase: Client, logger: logging.Logger) -> None:
    logger.info("\n🔄 Refreshing Materialized View (beer_info_view)...")
    try:
        sync_execute(supabase.rpc('refresh_beer_info_view'))
        logger.info("✅ View refreshed successfully!")
    except Exception as e:
        logger.warning(f"⚠️ Failed to refresh view: {e}")


# backend/src/core/db.py
from typing import Optional
from supabase import create_client, Client
from .config import settings

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
             raise ValueError("Supabase credentials not set in environment or .env")
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase_client

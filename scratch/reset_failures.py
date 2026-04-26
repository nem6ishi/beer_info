import asyncio
from backend.src.core.db import get_supabase_client

def reset_failures():
    supabase = get_supabase_client()
    res = supabase.table('untappd_search_failures').update({
        'search_attempts': 0,
        'last_failed_at': None
    }).eq('resolved', False).execute()
    
    print(f"Reset {len(res.data)} failures.")

if __name__ == "__main__":
    reset_failures()

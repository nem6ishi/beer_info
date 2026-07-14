import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

def fetch_beers(
    supabase: Any,
    mode: str,
    offset: int,
    db_fetch_limit: int,
    shop_filter: Optional[str] = None,
    name_filter: Optional[str] = None,
    skip_urls_for_backoff: Optional[Set[str]] = None,
    force: bool = False,
) -> List[Dict[str, Any]]:
    """Fetches candidates based on current mode."""
    if mode == 'missing':
        query: Any = supabase.table('beer_info_view') \
            .select('*') \
            .or_('untappd_url.is.null,untappd_url.ilike.%/search?%,untappd_beer_name.is.null') \
            .or_('product_type.eq.beer,product_type.is.null')
        if shop_filter:
            query = query.eq('shop', shop_filter)
        if name_filter:
            query = query.ilike('name', f'%{name_filter}%')
        res: Any = query.order('first_seen', desc=True).limit(db_fetch_limit).offset(offset).execute()
        beers = res.data or []
        
        if skip_urls_for_backoff:
            beers = [b for b in beers if b.get('url') not in skip_urls_for_backoff]
        return beers

    elif mode == 'refresh':
        logger.info(f"\n📂 Loading batch of REFRESH beers (offset={offset})...")
        query = supabase.table('beer_info_view') \
            .select('url, name, untappd_url, stock_status, untappd_fetched_at') \
            .not_.is_('untappd_url', 'null') \
            .neq('stock_status', 'Sold Out')
        if not (name_filter or force):
            cutoff_date: str = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
            query = query.or_(f'untappd_fetched_at.is.null,untappd_fetched_at.lt.{cutoff_date},untappd_beer_name.is.null')
        if shop_filter:
            query = query.eq('shop', shop_filter)
        if name_filter:
            query = query.ilike('name', f'%{name_filter}%')
        res = query.order('untappd_fetched_at', desc=False, nullsfirst=True).limit(db_fetch_limit).offset(offset).execute()
        return res.data or []

    elif mode == 'retry-failures':
        logger.info(f"\n📂 Loading unresolved failures from untappd_search_failures (offset={offset})...")
        query = supabase.table('untappd_search_failures') \
            .select('product_url, failure_reason, beer_name, brewery_name') \
            .eq('resolved', False)
        if name_filter:
            query = query.ilike('beer_name', f'%{name_filter}%')
        res = query.order('last_failed_at', desc=False).limit(db_fetch_limit).offset(offset).execute()
        urls = [f['product_url'] for f in (res.data or []) if f.get('product_url')]
        if not urls:
            return []
        b_query = supabase.table('beer_info_view').select('*').in_('url', urls)
        if shop_filter:
            b_query = b_query.eq('shop', shop_filter)
        b_res = b_query.execute()
        beer_map = {b['url']: b for b in (b_res.data or [])}
        beers = []
        for f in (res.data or []):
            b = beer_map.get(f['product_url'])
            if b:
                beers.append(b)
        return beers
    
    return []

def prefetch_gemini_untappd_urls(supabase: Any, urls: List[str]) -> Dict[str, str]:
    """Prefetch gemini_data cache to prevent N+1 queries."""
    if not urls:
        return {}
    try:
        gemini_res = supabase.table('gemini_data').select('url, untappd_url').in_('url', urls).execute()
        return {item['url']: item.get('untappd_url') for item in (gemini_res.data or []) if item.get('untappd_url')}
    except Exception as e:
        logger.warning(f"  ⚠️ Failed to prefetch gemini_data cache: {e}")
        return {}

def upsert_untappd_data(supabase: Any, untappd_payloads: List[Dict[str, Any]]) -> None:
    """Upsert to untappd_data table."""
    if untappd_payloads:
        deduped = {}
        for p in untappd_payloads:
            if p.get('untappd_url'):
                deduped[p['untappd_url']] = p
        payloads_to_save = list(deduped.values()) if deduped else untappd_payloads
        try:
            supabase.table('untappd_data').upsert(payloads_to_save).execute()
            logger.info(f"  💾 Saved {len(payloads_to_save)} items to untappd_data (Batch)")
        except Exception as e:
            logger.error(f"  ❌ Error saving to untappd_data (Batch): {e}")

def update_gemini_data_untappd_urls(supabase: Any, gemini_updates: List[Dict[str, Any]]) -> None:
    """Update untappd_url in gemini_data table."""
    if gemini_updates:
        success_count = 0
        for item in gemini_updates:
            try:
                supabase.table('gemini_data').update({'untappd_url': item['untappd_url']}).eq('url', item['url']).execute()
                success_count += 1
            except Exception as e:
                logger.error(f"  ⚠️ Error updating gemini_data for {item['url']}: {e}")
        logger.info(f"  💾 Updated {success_count} items in gemini_data (Batch)")

def update_scraped_beers_untappd_urls(supabase: Any, scraped_updates: List[Dict[str, Any]]) -> None:
    """Update untappd_url in scraped_beers table."""
    if scraped_updates:
        success_count = 0
        for item in scraped_updates:
            try:
                supabase.table('scraped_beers').update({'untappd_url': item['untappd_url']}).eq('url', item['url']).execute()
                success_count += 1
            except Exception as e:
                logger.error(f"  ❌ Error updating scraped_beers for {item['url']}: {e}")
        logger.info(f"  💾 Linked {success_count} items in scraped_beers (Batch)")

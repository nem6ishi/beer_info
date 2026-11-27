"""
Brewery Enrichment Script (Untappd)
Enriches the `breweries` table with details from Untappd.
Optimized to reduce N+1 queries by caching existing records.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set
from dateutil import parser as dateutil_parser

from ..core.db import get_supabase_client, refresh_materialized_view
from ..core.types import UntappdBreweryDetails
from ..services.untappd.http_client import scrape_brewery_details

logger: logging.Logger = logging.getLogger(__name__)


def _extract_brewery_numeric_id(url: Optional[str]) -> Optional[str]:
    """Extracts the trailing numeric Untappd brewery ID from '/w/<slug>/<id>' URLs."""
    if not url:
        return None
    m = re.search(r'/w/[^/]+/(\d+)(?:[/?#]|$)', url)
    return m.group(1) if m else None


def _fetch_all_rows_paginated(supabase: Any, table: str, columns: str, not_null_col: Optional[str] = None, order_col: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches all rows from a Supabase table using 1,000-row pagination."""
    rows: List[Dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        q = supabase.table(table).select(columns)
        if not_null_col:
            q = q.not_.is_(not_null_col, 'null')
        if order_col:
            q = q.order(order_col)
        res = q.range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


async def enrich_breweries(
    limit: int = 50,
    force: bool = False,
    target_urls: Optional[List[str]] = None
) -> None:
    """
    Enriches the `breweries` table with details from Untappd.
    """
    logger.info("=" * 70)
    logger.info(f"🏭 Brewery Enrichment (Limit: {limit}, Force: {force})")
    if target_urls:
        logger.info(f"🎯 Target: {len(target_urls)} specific breweries")
    logger.info("=" * 70)

    supabase: Any = get_supabase_client()

    # Cache existing breweries (paginated to handle >1,000 rows safely)
    logger.info("  🔍 Caching existing breweries from DB...")
    all_breweries_data: List[Dict[str, Any]] = _fetch_all_rows_paginated(
        supabase, 'breweries', 'id, untappd_url, name_en, updated_at', order_col='id'
    )

    breweries_by_url: Dict[str, Dict[str, Any]] = {
        b['untappd_url']: b for b in all_breweries_data if b.get('untappd_url')
    }
    breweries_by_name: Dict[str, Dict[str, Any]] = {
        b['name_en']: b for b in all_breweries_data if b.get('name_en')
    }
    breweries_by_numeric_id: Dict[str, Dict[str, Any]] = {}
    for b in all_breweries_data:
        bid = _extract_brewery_numeric_id(b.get('untappd_url'))
        if bid:
            breweries_by_numeric_id[bid] = b

    logger.info(f"    ✅ Cached {len(all_breweries_data)} breweries.")

    total_processed: int = 0
    any_db_changes: bool = False
    processed_urls: Set[str] = set()

    def _relink_untappd_data_url(old_url: str, canonical_url: str, label: str) -> bool:
        """Aligns untappd_data.untappd_brewery_url to the canonical breweries.untappd_url so joins succeed."""
        nonlocal any_db_changes
        try:
            supabase.table('untappd_data') \
                .update({'untappd_brewery_url': canonical_url}) \
                .eq('untappd_brewery_url', old_url) \
                .execute()
            any_db_changes = True
            logger.info(f"  🔗 Relinked untappd_data brewery URL for '{label}': {old_url} -> {canonical_url}")
            return True
        except Exception as e:
            logger.error(f"  ❌ Failed to relink untappd_data URL {old_url} -> {canonical_url}: {e}")
            return False

    # Helper to check freshness locally
    def should_process_url(url: str) -> bool:
        if force:
            return True
        existing: Optional[Dict[str, Any]] = breweries_by_url.get(url)
        if not existing:
            return True
        updated_at: Optional[str] = existing.get('updated_at')
        if not updated_at:
            return True
        try:
            last_update: datetime = dateutil_parser.parse(updated_at)
            # If updated in the last 7 days, skip
            if datetime.now(timezone.utc) - last_update < timedelta(days=7):
                return False
        except Exception:
            return True
        return True

    # Common processing block
    async def process_single_brewery(url: str) -> bool:
        nonlocal any_db_changes
        if url in processed_urls:
            return False

        # Fast-path: if URL is not in breweries_by_url, check if same numeric ID already exists under another slug
        if url not in breweries_by_url:
            num_id = _extract_brewery_numeric_id(url)
            if num_id and num_id in breweries_by_numeric_id:
                canonical = breweries_by_numeric_id[num_id]
                canonical_url = canonical.get('untappd_url')
                if canonical_url and canonical_url != url:
                    _relink_untappd_data_url(url, canonical_url, canonical.get('name_en') or num_id)
                    processed_urls.add(url)
                    return True

        if not should_process_url(url):
            logger.info(f"  ⏭️  Skipped (recently updated): {url}")
            processed_urls.add(url)
            return False

        logger.info(f"  🔄 Enriching: {url}")
        await asyncio.sleep(2)  # Rate limit
        details: UntappdBreweryDetails = await scrape_brewery_details(url)

        if not details:
            logger.warning(f"  ⚠️ Failed to scrape: {url}")
            processed_urls.add(url)
            return False

        brewery_name: Optional[str] = (details.get('brewery_name') or '').strip() or None
        invalid_names = ("we couldn't find that page", "page not found", "404 not found", "just a moment")
        if not brewery_name or any(bad in brewery_name.lower() for bad in invalid_names):
            logger.warning(f"  ⚠️ Invalid or 404 brewery name ('{brewery_name}') for: {url}")
            processed_urls.add(url)
            return False

        # Check by name in cache
        target_id: Optional[Any] = None
        existing_by_name: Optional[Dict[str, Any]] = breweries_by_name.get(brewery_name)

        if existing_by_name:
            existing_url: Optional[str] = existing_by_name.get('untappd_url')
            # Same brewery but different URL (e.g., vanity URL vs /w/ URL or changed slug):
            # Relink untappd_data to the canonical existing_url so beer_info_view logo JOIN works.
            if existing_url and existing_url != url:
                logger.info(f"  🔄 '{brewery_name}' already exists with canonical URL: {existing_url}. Relinking untappd_data...")
                _relink_untappd_data_url(url, existing_url, brewery_name)
                processed_urls.add(url)
                return True
            elif not existing_url:
                logger.info(f"  📝 Matching to existing record with null URL: {brewery_name}")
                target_id = existing_by_name.get('id')
            elif existing_url == url:
                target_id = existing_by_name.get('id')

        # If not found by name, try by URL just in case name changed
        if not target_id:
            existing_by_url: Optional[Dict[str, Any]] = breweries_by_url.get(url)
            if existing_by_url:
                target_id = existing_by_url.get('id')

        payload: Dict[str, Any] = {
            'untappd_url': url,
            'name_en': brewery_name,
            'location': details.get('location'),
            'brewery_type': details.get('brewery_type'),
            'website': details.get('website'),
            'logo_url': details.get('logo_url'),
            'stats': details.get('stats'),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }

        try:
            if target_id:
                # Update existing record
                supabase.table('breweries').update(payload).eq('id', target_id).execute()
                logger.info(f"  ✅ Updated: {brewery_name}")
            else:
                # Insert new record
                res: Any = supabase.table('breweries').insert(payload).execute()
                if res.data:
                    new_rec: Dict[str, Any] = res.data[0]
                    breweries_by_url[url] = new_rec
                    breweries_by_name[brewery_name] = new_rec
                    bid = _extract_brewery_numeric_id(url)
                    if bid:
                        breweries_by_numeric_id[bid] = new_rec
                logger.info(f"  ✅ Inserted: {brewery_name}")

            any_db_changes = True
            processed_urls.add(url)
            return True
        except Exception as e:
            logger.error(f"  ❌ Error saving {url}: {e}")
            return False

    # PRIORITY 1: Process target_urls first (these don't count against limit)
    if target_urls:
        logger.info(f"\n🎯 PRIORITY: Processing {len(target_urls)} target breweries...")
        for url in target_urls:
            if await process_single_brewery(url):
                total_processed += 1
        logger.info(f"\n✅ Priority processing complete. Processed {total_processed} target breweries.")

    # PRIORITY 2: Process additional breweries from untappd_data (up to limit)
    if total_processed < limit:
        remaining_limit: int = limit - total_processed
        logger.info(f"\n📂 Processing additional breweries from database (up to {remaining_limit})...")

        # Collect ALL distinct brewery URLs from untappd_data via pagination
        logger.info("  🔍 Collecting unique brewery URLs from beer data (paginated)...")
        data: List[Dict[str, Any]] = _fetch_all_rows_paginated(
            supabase, 'untappd_data', 'untappd_brewery_url', not_null_col='untappd_brewery_url', order_col='untappd_url'
        )
        if not data:
            logger.info("  ✨ No brewery URLs found in untappd_data.")
        else:
            all_unique_urls: List[str] = list(dict.fromkeys(
                item['untappd_brewery_url'] for item in data if item.get('untappd_brewery_url')
            ))
            # Prioritize unregistered brewery URLs before refreshing already-known ones
            unregistered_urls: List[str] = [u for u in all_unique_urls if u not in breweries_by_url]
            registered_urls: List[str] = [u for u in all_unique_urls if u in breweries_by_url]
            ordered_urls: List[str] = unregistered_urls + registered_urls

            logger.info(
                f"  Found {len(all_unique_urls)} unique brewery URLs "
                f"({len(unregistered_urls)} unregistered, {len(registered_urls)} registered)."
            )

            for url in ordered_urls:
                if total_processed >= limit:
                    break

                if await process_single_brewery(url):
                    total_processed += 1

    if any_db_changes:
        refresh_materialized_view(supabase, logger)

    logger.info(f"\n✨ Brewery enrichment completed. Processed {total_processed} breweries.")

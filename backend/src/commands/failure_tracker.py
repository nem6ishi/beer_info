"""
Helper functions for recording Untappd search failures.
"""
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def record_enrichment_failure(
    supabase,
    product_url: str,
    failure_reason: str,
    brewery_name: Optional[str] = None,
    beer_name: Optional[str] = None,
    beer_name_jp: Optional[str] = None,
    error_message: Optional[str] = None
):
    """
    Records or updates an enrichment failure in the database.
    This replaces/generalizes the old record_search_failure.
    
    Args:
        supabase: Supabase client instance
        product_url: The product URL from scraped_beers
        failure_reason: Category of failure (gemini_error, no_results, untappd_scrape_error, etc.)
        brewery_name: Brewery name used in search/process (optional)
        beer_name: Beer name used in search/process (optional)
        beer_name_jp: Japanese beer name (optional)
        error_message: Detailed error message
    """
    try:
        # Check if failure already exists (resolved=False)
        existing = supabase.table('untappd_search_failures') \
            .select('id, search_attempts') \
            .eq('product_url', product_url) \
            .eq('resolved', False) \
            .maybe_single() \
            .execute()
        
        now = datetime.now(timezone.utc).isoformat()
        
        if existing and existing.data:
            # Update existing failure record
            supabase.table('untappd_search_failures') \
                .update({
                    'search_attempts': existing.data['search_attempts'] + 1,
                    'last_failed_at': now,
                    'failure_reason': failure_reason,
                    'last_error_message': error_message,
                    'brewery_name': brewery_name,
                    'beer_name': beer_name,
                    'beer_name_jp': beer_name_jp
                }) \
                .eq('id', existing.data['id']) \
                .execute()
            logger.info(f"  📝 Updated failure record (attempt {existing.data['search_attempts'] + 1}): {failure_reason}")
        else:
            # Insert new failure record
            supabase.table('untappd_search_failures') \
                .insert({
                    'product_url': product_url,
                    'brewery_name': brewery_name,
                    'beer_name': beer_name,
                    'beer_name_jp': beer_name_jp,
                    'failure_reason': failure_reason,
                    'search_attempts': 1,
                    'last_error_message': error_message,
                    'first_failed_at': now,
                    'last_failed_at': now,
                    'resolved': False
                }) \
                .execute()
            logger.info(f"  📝 Recorded new enrichment failure: {failure_reason}")
            
    except Exception as e:
        logger.error(f"  ⚠️  Error recording failure: {e}")

# Maintain backward compatibility
def record_search_failure(*args, **kwargs):
    return record_enrichment_failure(*args, **kwargs)


def resolve_search_failure(supabase, product_url: str):
    """
    Marks a search failure as resolved when the beer is successfully linked.
    
    Args:
        supabase: Supabase client instance
        product_url: The product URL that was successfully resolved
    """
    try:
        now = datetime.now(timezone.utc).isoformat()
        result = supabase.table('untappd_search_failures') \
            .update({
                'resolved': True,
                'resolved_at': now
            }) \
            .eq('product_url', product_url) \
            .eq('resolved', False) \
            .execute()
        
        if result.data:
            logger.info(f"  ✅ Marked failure as resolved")
    except Exception as e:
        logger.error(f"  ⚠️ Error resolving failure: {e}")

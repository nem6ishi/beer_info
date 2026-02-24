"""
Validation functions for matching beer/brewery names in Untappd search results.
Split from searcher.py for better modularity.
"""
import re
import logging
from bs4 import BeautifulSoup
from .text_utils import normalize_for_comparison, normalize_ordinals, strip_for_core_comparison, clean_brewery_name

logger = logging.getLogger(__name__)

# Loaded dynamically by searcher.py – injected here for alias lookup
_BREWERY_ALIASES: dict = {}

def set_brewery_aliases(aliases: dict) -> None:
    """Set brewery aliases dict (called from searcher after loading aliases.json)."""
    global _BREWERY_ALIASES
    _BREWERY_ALIASES = aliases


def validate_beer_match(result_element: BeautifulSoup, expected_beer: str) -> bool:
    """Checks if the beer name in the search result matches the expected beer."""
    if not expected_beer:
        return True

    name_tag = result_element.select_one('.name a')
    if not name_tag:
        return False

    result_beer = name_tag.get_text(strip=True)
    rb_norm = normalize_for_comparison(result_beer)
    eb_norm = normalize_for_comparison(expected_beer)

    # 1. Direct inclusion check
    if rb_norm in eb_norm or eb_norm in rb_norm:
        logger.info(f"  [Validation] Beer MATCH: '{result_beer}' matches '{expected_beer}'")
        return True

    # 2. Ordinal normalization check (11th -> eleventh, etc.)
    rb_ord = normalize_for_comparison(normalize_ordinals(result_beer))
    eb_ord = normalize_for_comparison(normalize_ordinals(expected_beer))
    if rb_ord in eb_ord or eb_ord in rb_ord:
        logger.info(f"  [Validation] Beer MATCH (Ordinal): '{result_beer}' matches '{expected_beer}'")
        return True

    # 3. Core name comparison: strip year, dashes, style suffixes
    rb_core = normalize_for_comparison(strip_for_core_comparison(result_beer))
    eb_core = normalize_for_comparison(strip_for_core_comparison(expected_beer))
    if rb_core and eb_core and (rb_core in eb_core or eb_core in rb_core):
        logger.info(f"  [Validation] Beer MATCH (Core): '{result_beer}' matches '{expected_beer}'")
        return True

    # 4. Combined: ordinal + core stripping
    rb_ord_core = normalize_for_comparison(strip_for_core_comparison(normalize_ordinals(result_beer)))
    eb_ord_core = normalize_for_comparison(strip_for_core_comparison(normalize_ordinals(expected_beer)))
    if rb_ord_core and eb_ord_core and (rb_ord_core in eb_ord_core or eb_ord_core in rb_ord_core):
        logger.info(f"  [Validation] Beer MATCH (Ordinal+Core): '{result_beer}' matches '{expected_beer}'")
        return True

    logger.info(f"  [Validation] Beer FAIL: '{result_beer}' ({rb_norm}) != '{expected_beer}' ({eb_norm})")
    return False


def validate_brewery_match(result_element: BeautifulSoup, expected_brewery: str) -> bool:
    """
    Checks if the brewery name in the search result matches the expected brewery.
    Uses normalized comparison, aliases, and collab logic.
    """
    if not expected_brewery:
        return True

    brewery_tag = result_element.select_one('.brewery')
    if not brewery_tag:
        return False

    result_brewery = brewery_tag.get_text(strip=True)
    rb_norm = normalize_for_comparison(result_brewery)
    eb_norm = normalize_for_comparison(expected_brewery)

    # 1. Normalization Check
    if rb_norm in eb_norm or eb_norm in rb_norm:
        logger.info(f"  [Validation] Brewery MATCH (Norm): '{result_brewery}' matches '{expected_brewery}'")
        return True

    # 2. Cleaned Name Check (removes brewery suffixes like 'brewing', etc.)
    cleaned_result = clean_brewery_name(result_brewery)
    cleaned_expected = clean_brewery_name(expected_brewery)
    cr_norm = normalize_for_comparison(cleaned_result)
    ce_norm = normalize_for_comparison(cleaned_expected)
    if cr_norm and ce_norm and (cr_norm in ce_norm or ce_norm in cr_norm):
        logger.info(f"  [Validation] Brewery MATCH (Cleaned): '{result_brewery}' matches '{expected_brewery}'")
        return True

    # 3. Alias Check
    if expected_brewery in _BREWERY_ALIASES:
        for alias in _BREWERY_ALIASES[expected_brewery]:
            alias_norm = normalize_for_comparison(alias)
            if alias_norm in rb_norm:
                logger.info(f"  [Validation] Brewery MATCH (Alias): '{result_brewery}' matches alias '{alias}'")
                return True

    # 4. Collaboration Check (x, ×, /)
    if any(sep in expected_brewery for sep in [' x ', ' x', 'x ', '×', '/']):
        parts = re.split(r'\s*[x×/]\s*', expected_brewery)
        for part in parts:
            if not part:
                continue
            part_norm = normalize_for_comparison(part)
            if part_norm and (part_norm in rb_norm or rb_norm in part_norm):
                logger.info(f"  [Validation] Brewery MATCH (Collab): '{result_brewery}' matches part '{part}'")
                return True
            if part in _BREWERY_ALIASES:
                for alias in _BREWERY_ALIASES[part]:
                    alias_norm = normalize_for_comparison(alias)
                    if alias_norm and (alias_norm in rb_norm or rb_norm in alias_norm):
                        logger.info(f"  [Validation] Brewery MATCH (Collab Alias): alias '{alias}'")
                        return True

    logger.info(f"  [Validation] Brewery FAIL: '{result_brewery}' != '{expected_brewery}'")
    return False

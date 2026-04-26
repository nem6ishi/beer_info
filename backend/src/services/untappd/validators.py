"""
Validation functions for matching beer/brewery names in Untappd search results.
Split from searcher.py for better modularity.
"""
import re
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup, Tag
from .text_utils import (
    normalize_for_comparison, normalize_ordinals, strip_for_core_comparison,
    clean_brewery_name, has_variant_mismatch, expand_abbreviations,
)

logger = logging.getLogger(__name__)

# Loaded dynamically by searcher.py – injected here for alias lookup
_BREWERY_ALIASES: Dict[str, List[str]] = {}

def set_brewery_aliases(aliases: Dict[str, List[str]]) -> None:
    """Set brewery aliases dict (called from searcher after loading aliases.json)."""
    global _BREWERY_ALIASES
    _BREWERY_ALIASES = aliases


def validate_beer_match(result_element: Tag, expected_beer: str) -> bool:
    """Checks if the beer name in the search result matches the expected beer."""
    return score_beer_match(result_element, expected_beer) > 0


def score_beer_match(result_element: Tag, expected_beer: str) -> int:
    """
    Scores how well a search result matches the expected beer name.
    Returns a score (higher = better match):
      - 100: Exact normalized match
      -  95: Exact match after abbreviation expansion (DDH=Double Dry Hopped)
      -  90: Direct inclusion match (no variant mismatch)
      -  80: Ordinal-normalized match
      -  70: Core comparison match (no variant mismatch)
      -  60: Ordinal + Core match (no variant mismatch)
      -   0: No match or variant mismatch detected
    """
    if not expected_beer:
        return 100  # No expected name = any match is fine

    name_tag = result_element.select_one('.name a')
    if not name_tag:
        return 0

    result_beer: str = name_tag.get_text(strip=True)
    rb_norm: str = normalize_for_comparison(result_beer)
    eb_norm: str = normalize_for_comparison(expected_beer)

    # 1. Exact normalized match
    if rb_norm == eb_norm:
        logger.info(f"  [Validation] Beer EXACT MATCH: '{result_beer}' == '{expected_beer}'")
        return 100

    # 1b. Exact match after abbreviation expansion (DDH ↔ Double Dry Hopped)
    rb_expanded: str = normalize_for_comparison(result_beer, expand_abbr=True)
    eb_expanded: str = normalize_for_comparison(expected_beer, expand_abbr=True)
    if rb_expanded == eb_expanded:
        logger.info(f"  [Validation] Beer MATCH (Abbr Expanded, 95): '{result_beer}' matches '{expected_beer}'")
        return 95

    # 2. Direct inclusion check (with variant guard)
    if rb_norm in eb_norm or eb_norm in rb_norm:
        if has_variant_mismatch(result_beer, expected_beer):
            logger.debug(f"  [Validation] Beer BLOCKED (Variant): '{result_beer}' vs '{expected_beer}'")
        else:
            logger.info(f"  [Validation] Beer MATCH (90): '{result_beer}' matches '{expected_beer}'")
            return 90

    # 2b. Direct inclusion after abbreviation expansion
    if rb_expanded in eb_expanded or eb_expanded in rb_expanded:
        if not has_variant_mismatch(result_beer, expected_beer):
            logger.info(f"  [Validation] Beer MATCH (Abbr Inclusion, 88): '{result_beer}' matches '{expected_beer}'")
            return 88

    # 3. Ordinal normalization check (11th -> eleventh, etc.)
    rb_ord: str = normalize_for_comparison(normalize_ordinals(result_beer))
    eb_ord: str = normalize_for_comparison(normalize_ordinals(expected_beer))
    if rb_ord == eb_ord:
        logger.info(f"  [Validation] Beer MATCH (Ordinal Exact, 85): '{result_beer}' matches '{expected_beer}'")
        return 85
    if rb_ord in eb_ord or eb_ord in rb_ord:
        if not has_variant_mismatch(result_beer, expected_beer):
            logger.info(f"  [Validation] Beer MATCH (Ordinal, 80): '{result_beer}' matches '{expected_beer}'")
            return 80

    # 4. Core name comparison: strip year, dashes, style suffixes
    rb_core: str = normalize_for_comparison(strip_for_core_comparison(result_beer))
    eb_core: str = normalize_for_comparison(strip_for_core_comparison(expected_beer))
    if rb_core and eb_core:
        if rb_core == eb_core:
            # Core names are identical — only variant modifiers differ
            if has_variant_mismatch(result_beer, expected_beer):
                logger.debug(f"  [Validation] Beer BLOCKED (Core Exact + Variant): '{result_beer}' vs '{expected_beer}'")
            else:
                logger.info(f"  [Validation] Beer MATCH (Core Exact, 75): '{result_beer}' matches '{expected_beer}'")
                return 75
        elif rb_core in eb_core or eb_core in rb_core:
            if has_variant_mismatch(result_beer, expected_beer):
                logger.debug(f"  [Validation] Beer BLOCKED (Core + Variant): '{result_beer}' vs '{expected_beer}'")
            else:
                logger.info(f"  [Validation] Beer MATCH (Core, 70): '{result_beer}' matches '{expected_beer}'")
                return 70

    # 5. Combined: ordinal + core stripping
    rb_ord_core: str = normalize_for_comparison(strip_for_core_comparison(normalize_ordinals(result_beer)))
    eb_ord_core: str = normalize_for_comparison(strip_for_core_comparison(normalize_ordinals(expected_beer)))
    if rb_ord_core and eb_ord_core and (rb_ord_core in eb_ord_core or eb_ord_core in rb_ord_core):
        if has_variant_mismatch(result_beer, expected_beer):
            logger.debug(f"  [Validation] Beer BLOCKED (Ordinal+Core + Variant): '{result_beer}' vs '{expected_beer}'")
        else:
            logger.info(f"  [Validation] Beer MATCH (Ordinal+Core, 60): '{result_beer}' matches '{expected_beer}'")
            return 60

    logger.info(f"  [Validation] Beer FAIL: '{result_beer}' ({rb_norm}) != '{expected_beer}' ({eb_norm})")
    return 0


def validate_brewery_match(result_element: Tag, expected_brewery: str) -> bool:
    """
    Checks if the brewery name in the search result matches the expected brewery.
    Uses normalized comparison, aliases, and collab logic.
    """
    if not expected_brewery:
        return True

    brewery_tag = result_element.select_one('.brewery')
    if not brewery_tag:
        return False

    result_brewery: str = brewery_tag.get_text(strip=True)
    rb_norm: str = normalize_for_comparison(result_brewery)
    eb_norm: str = normalize_for_comparison(expected_brewery)

    # 1. Normalization Check
    if rb_norm in eb_norm or eb_norm in rb_norm:
        logger.info(f"  [Validation] Brewery MATCH (Norm): '{result_brewery}' matches '{expected_brewery}'")
        return True

    # 2. Cleaned Name Check (removes brewery suffixes like 'brewing', etc.)
    cleaned_result: str = clean_brewery_name(result_brewery)
    cleaned_expected: str = clean_brewery_name(expected_brewery)
    cr_norm: str = normalize_for_comparison(cleaned_result)
    ce_norm: str = normalize_for_comparison(cleaned_expected)
    if cr_norm and ce_norm and (cr_norm in ce_norm or ce_norm in cr_norm):
        logger.info(f"  [Validation] Brewery MATCH (Cleaned): '{result_brewery}' matches '{expected_brewery}'")
        return True

    # 3. Alias Check
    if expected_brewery in _BREWERY_ALIASES:
        for alias in _BREWERY_ALIASES[expected_brewery]:
            alias_norm: str = normalize_for_comparison(alias)
            if alias_norm in rb_norm:
                logger.info(f"  [Validation] Brewery MATCH (Alias): '{result_brewery}' matches alias '{alias}'")
                return True

    # 4. Collaboration Check (x, ×, /)
    if any(sep in expected_brewery for sep in [' x ', ' x', 'x ', '×', '/']):
        parts: List[str] = re.split(r'\s*[x×/]\s*', expected_brewery)
        for part in parts:
            if not part:
                continue
            part_norm: str = normalize_for_comparison(part)
            if part_norm and (part_norm in rb_norm or rb_norm in part_norm):
                logger.info(f"  [Validation] Brewery MATCH (Collab): '{result_brewery}' matches part '{part}'")
                return True
            if part in _BREWERY_ALIASES:
                for alias in _BREWERY_ALIASES[part]:
                    alias_norm_sub: str = normalize_for_comparison(alias)
                    if alias_norm_sub and (alias_norm_sub in rb_norm or rb_norm in alias_norm_sub):
                        logger.info(f"  [Validation] Brewery MATCH (Collab Alias): alias '{alias}'")
                        return True

    logger.info(f"  [Validation] Brewery FAIL: '{result_brewery}' != '{expected_brewery}'")
    return False

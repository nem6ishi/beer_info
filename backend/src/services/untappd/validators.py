"""
Validation functions for matching beer/brewery names in Untappd search results.
Split from searcher.py for better modularity.
"""
import re
import logging
from typing import Dict, List, Optional, Union, Any
from difflib import SequenceMatcher
from bs4 import Tag
from .text_utils import (
    normalize_for_comparison, normalize_ordinals, normalize_numbers_and_romans,
    normalize_singular_plural,
    strip_for_core_comparison, clean_brewery_name, clean_beer_name, has_variant_mismatch, COLLAB_SPLIT_PATTERN,
)

logger = logging.getLogger(__name__)

# Loaded dynamically by searcher.py – injected here for alias lookup
_BREWERY_ALIASES: Dict[str, List[str]] = {}


def set_brewery_aliases(aliases: Dict[str, List[str]]) -> None:
    """Set brewery aliases dict (called from searcher after loading aliases.json)."""
    global _BREWERY_ALIASES
    _BREWERY_ALIASES = aliases


def get_name_parts(name: str) -> List[str]:
    """Extracts the full name, the part before parentheses, and any parts inside parentheses."""
    if not name:
        return []
    parts = [name]
    outside = re.sub(r'\s*[（(][^）)]*[）)]\s*', ' ', name).strip()
    if outside and outside != name:
        parts.append(outside)
    insides = re.findall(r'[（(]([^）)]+)[）)]', name)
    for inc in insides:
        inc_clean = inc.strip()
        if inc_clean and inc_clean not in parts:
            parts.append(inc_clean)
    return parts


def _is_safe_substring_match(str_a: str, str_b: str, expected_brewery: Optional[str] = None) -> bool:
    """Checks if one string being inside the other is a safe match without major extra unrelated words."""
    if not str_a or not str_b:
        return False
    if str_a == str_b:
        return True
    shorter, longer = (str_a, str_b) if len(str_a) <= len(str_b) else (str_b, str_a)
    if not (shorter in longer):
        return False
    if len(shorter) < 4:
        return False
    ratio = SequenceMatcher(None, shorter, longer).ratio()
    if ratio >= 0.78:
        return True
    # If ratio < 0.78, check if the extra portion is purely style/variant/number/brewery noise
    remainder = longer.replace(shorter, "")
    allowed_noise = ["barrel", "aged", "sour", "ale", "stout", "ipa", "collaborat", "batch", "edition", "series", "vol", "ver", "double", "triple", "imperial", "hazy", "neipa", "shigakogen", "tamamura", "honten"]
    if any(n in remainder for n in allowed_noise):
        return True
    if expected_brewery:
        brew_norm = normalize_for_comparison(expected_brewery)
        if brew_norm and (brew_norm in remainder or remainder in brew_norm):
            return True
        for b_word in re.findall(r'[a-z0-9]+', expected_brewery.lower()):
            if len(b_word) >= 3 and b_word in remainder:
                return True
        for alias_list in _BREWERY_ALIASES.values():
            if any(normalize_for_comparison(expected_brewery) == normalize_for_comparison(a) for a in alias_list):
                for a in alias_list:
                    a_norm = normalize_for_comparison(a)
                    if a_norm and len(a_norm) >= 4 and (a_norm in remainder or remainder in a_norm):
                        return True
    return False


def validate_beer_match(result_element: Union[Tag, Dict[str, Any]], expected_beer: str, expected_brewery: Optional[str] = None) -> bool:
    """
    Returns True if the Untappd beer element matches expected_beer and expected_brewery.
    Calls score_beer_match internally and requires score > 0.
    """
    return score_beer_match(result_element, expected_beer, expected_brewery) > 0


def score_beer_match(result_elem: Union[Tag, Dict[str, Any]], expected_beer: str, expected_brewery: Optional[str] = None) -> int:
    """
    Scores how well an Untappd beer element matches expected_beer (and expected_brewery).
    Returns an integer from 0 to 100:
      - 100: Exact match after basic normalization
      -  95: Exact match after abbreviation expansion
      -  90: Direct inclusion match
      -  85: Exact match after ordinal normalization (11th -> eleventh)
      -  80: Substring match after ordinal normalization
      -  75: Exact match after core name stripping (no year, no style suffix)
      -  70: Substring match after core name stripping
      -  60: Substring match after ordinal + core stripping
      -  50: Part/Token exact or inclusion match (parentheses splitting)
      -   0: No acceptable match or variant mismatch detected
    """
    if not result_elem:
        return 0
    if not expected_beer:
        return 100

    if expected_brewery and not validate_brewery_match(result_elem, expected_brewery):
        logger.debug(f"  [Validation] Beer BLOCKED (Brewery Mismatch): expected brewery '{expected_brewery}'")
        return 0

    if isinstance(result_elem, dict):
        result_beer = result_elem.get('beer_name') or result_elem.get('name') or ''
        if not result_beer:
            return 0
        style_text = (result_elem.get('style') or '').lower()
    else:
        name_tag: Optional[Tag] = result_elem.select_one('.name a')
        if not name_tag:
            return 0
        result_beer = name_tag.get_text(strip=True)
        style_tag = result_elem.select_one('.style')
        style_text = style_tag.get_text(strip=True).lower() if style_tag else ""
    
    # 0. Check variant mismatch right upfront
    if has_variant_mismatch(result_beer, expected_beer):
        logger.debug(f"  [Validation] Beer BLOCKED (Variant Mismatch): '{result_beer}' vs '{expected_beer}'")
        return 0

    rb_norm: str = normalize_for_comparison(result_beer)
    eb_norm: str = normalize_for_comparison(expected_beer)

    if not rb_norm or not eb_norm:
        return 0

    # Check distinct keyword/style clashes if names are not exact matches
    if rb_norm != eb_norm:
        eb_words = set(re.findall(r'[a-z0-9]+', expected_beer.lower()))
        rb_words = set(re.findall(r'[a-z0-9]+', result_beer.lower()))
        style_words = set(re.findall(r'[a-z0-9]+', style_text))

        # Block New Engi-land vs Engi!? cross-matching on Shiga Kogen
        if 'engi' in eb_words and ('engiland' in rb_norm or 'land' in rb_words or 'new' in rb_words) and 'engiland' not in eb_norm and 'land' not in eb_words:
            logger.debug(f"  [Validation] Beer BLOCKED (Engi vs New Engi-land clash): '{result_beer}' vs '{expected_beer}'")
            return 0
        if ('engiland' in eb_norm or 'land' in eb_words or 'new' in eb_words) and 'engi' in rb_words and 'engiland' not in rb_norm and 'land' not in rb_words:
            logger.debug(f"  [Validation] Beer BLOCKED (New Engi-land vs Engi clash): '{result_beer}' vs '{expected_beer}'")
            return 0

        for kw in ['engi', 'weizen', 'stout', 'porter', 'pilsner', 'saison', 'barleywine', 'gose', 'keller']:
            if kw in eb_words:
                if kw not in rb_words and kw not in style_words:
                    # For distinctive brand/style keywords like engi or completely clashing styles, block
                    if kw == 'engi' or ('ipa' in style_words and kw in ['weizen', 'stout', 'porter', 'pilsner']):
                        logger.debug(f"  [Validation] Beer BLOCKED (Keyword/Style Clash '{kw}'): '{result_beer}' vs '{expected_beer}'")
                        return 0

    # 1. Exact match after standard normalization
    if rb_norm == eb_norm:
        logger.info(f"  [Validation] Beer MATCH (Exact, 100): '{result_beer}' matches '{expected_beer}'")
        return 100

    # 1b. Exact match after abbreviation expansion (e.g. BA -> Barrel Aged, DDH -> Double Dry Hopped)
    rb_expanded: str = normalize_for_comparison(result_beer, expand_abbr=True)
    eb_expanded: str = normalize_for_comparison(expected_beer, expand_abbr=True)
    if rb_expanded == eb_expanded:
        logger.info(f"  [Validation] Beer MATCH (Abbr Expanded, 95): '{result_beer}' matches '{expected_beer}'")
        return 95

    # 2. Direct inclusion check (with variant guard)
    if _is_safe_substring_match(rb_norm, eb_norm, expected_brewery):
        logger.info(f"  [Validation] Beer MATCH (90): '{result_beer}' matches '{expected_beer}'")
        return 90

    # 2b. Direct inclusion after abbreviation expansion
    if _is_safe_substring_match(rb_expanded, eb_expanded, expected_brewery):
        logger.info(f"  [Validation] Beer MATCH (Abbr Inclusion, 88): '{result_beer}' matches '{expected_beer}'")
        return 88

    # 3. Ordinal normalization check (11th -> eleventh, etc.)
    rb_ord: str = normalize_for_comparison(normalize_ordinals(result_beer))
    eb_ord: str = normalize_for_comparison(normalize_ordinals(expected_beer))
    if rb_ord == eb_ord:
        logger.info(f"  [Validation] Beer MATCH (Ordinal Exact, 85): '{result_beer}' matches '{expected_beer}'")
        return 85
    if _is_safe_substring_match(rb_ord, eb_ord, expected_brewery):
        logger.info(f"  [Validation] Beer MATCH (Ordinal, 80): '{result_beer}' matches '{expected_beer}'")
        return 80

    # 3b. Number & Roman numeral normalization check (III / Three / Ⅲ -> 3)
    rb_num: str = normalize_for_comparison(normalize_numbers_and_romans(result_beer))
    eb_num: str = normalize_for_comparison(normalize_numbers_and_romans(expected_beer))
    if rb_num == eb_num:
        logger.info(f"  [Validation] Beer MATCH (Number/Roman Exact, 85): '{result_beer}' matches '{expected_beer}'")
        return 85
    if _is_safe_substring_match(rb_num, eb_num, expected_brewery):
        logger.info(f"  [Validation] Beer MATCH (Number/Roman, 80): '{result_beer}' matches '{expected_beer}'")
        return 80

    # 3c. Singular/Plural normalization check (Fruits -> Fruit)
    rb_pl: str = normalize_for_comparison(normalize_singular_plural(result_beer))
    eb_pl: str = normalize_for_comparison(normalize_singular_plural(expected_beer))
    if rb_pl == eb_pl:
        logger.info(f"  [Validation] Beer MATCH (Singular/Plural Exact, 85): '{result_beer}' matches '{expected_beer}'")
        return 85
    if _is_safe_substring_match(rb_pl, eb_pl, expected_brewery):
        logger.info(f"  [Validation] Beer MATCH (Singular/Plural, 80): '{result_beer}' matches '{expected_beer}'")
        return 80

    # 4. Core name comparison: clean name, strip year, dashes, style suffixes
    rb_clean = clean_beer_name(result_beer)
    eb_clean = clean_beer_name(expected_beer)
    rb_core: str = normalize_for_comparison(strip_for_core_comparison(rb_clean))
    eb_core: str = normalize_for_comparison(strip_for_core_comparison(eb_clean))
    if rb_core and eb_core:
        if rb_core == eb_core:
            logger.info(f"  [Validation] Beer MATCH (Core Exact, 75): '{result_beer}' matches '{expected_beer}'")
            return 75
        elif _is_safe_substring_match(rb_core, eb_core, expected_brewery):
            logger.info(f"  [Validation] Beer MATCH (Core, 70): '{result_beer}' matches '{expected_beer}'")
            return 70

    # 5. Combined: ordinal + number/roman + singular/plural + core stripping
    rb_ord_core: str = normalize_for_comparison(strip_for_core_comparison(normalize_singular_plural(normalize_numbers_and_romans(normalize_ordinals(rb_clean)))))
    eb_ord_core: str = normalize_for_comparison(strip_for_core_comparison(normalize_singular_plural(normalize_numbers_and_romans(normalize_ordinals(eb_clean)))))
    if rb_ord_core and eb_ord_core and _is_safe_substring_match(rb_ord_core, eb_ord_core, expected_brewery):
        logger.info(f"  [Validation] Beer MATCH (Ordinal+Core, 60): '{result_beer}' matches '{expected_beer}'")
        return 60

    # 6. Part / Token Inclusion Check (for multilingual or parenthesized titles like "Doron (どろん)" vs "Ise Shima Doron")
    rb_parts = get_name_parts(rb_clean)
    eb_parts = get_name_parts(eb_clean)
    for rp in rb_parts:
        for ep in eb_parts:
            rp_norm = normalize_for_comparison(strip_for_core_comparison(rp))
            ep_norm = normalize_for_comparison(strip_for_core_comparison(ep))
            if not rp_norm or not ep_norm:
                continue
            if (rp_norm.isascii() and len(rp_norm) < 3) or len(rp_norm) < 2:
                continue
            if (ep_norm.isascii() and len(ep_norm) < 3) or len(ep_norm) < 2:
                continue
            if rp_norm == ep_norm or _is_safe_substring_match(rp_norm, ep_norm, expected_brewery):
                if not has_variant_mismatch(result_beer, expected_beer):
                    logger.info(f"  [Validation] Beer MATCH (Part/Token Inclusion, 75): '{rp}' matches '{ep}'")
                    return 75

    # 7. Fuzzy Match / Typo Tolerance (for minor spelling errors like "Hopwierd" vs "Hopwired")
    if len(rb_core) >= 4 and len(eb_core) >= 4:
        ratio = SequenceMatcher(None, rb_core, eb_core).ratio()
        if ratio >= 0.82:
            if not has_variant_mismatch(result_beer, expected_beer):
                logger.info(f"  [Validation] Beer MATCH (Fuzzy Typo, 70): '{result_beer}' ≈ '{expected_beer}' (ratio={ratio:.2f})")
                return 70

    logger.info(f"  [Validation] Beer FAIL: '{result_beer}' ({rb_norm}) != '{expected_beer}' ({eb_norm})")
    return 0


def validate_brewery_match(result_element: Union[Tag, Dict[str, Any]], expected_brewery: str) -> bool:
    """
    Checks if the brewery name in the search result matches the expected brewery.
    Uses normalized comparison, aliases, and collab logic.
    """
    if not expected_brewery:
        return True

    if isinstance(result_element, dict):
        result_brewery = result_element.get('brewery_name') or result_element.get('brewery') or ''
        if not result_brewery:
            return True
    else:
        brewery_tag = result_element.select_one('.brewery')
        if not brewery_tag:
            return True
        result_brewery = brewery_tag.get_text(strip=True)

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

    # 4. Collaboration Check (x, ×, /, &)
    if any(sep in expected_brewery for sep in [' x ', ' X ', 'x', 'X', '×', '/', '&', '+']):
        # Treat both target and expected breweries as potential lists of collaborators
        parts: List[str] = re.split(COLLAB_SPLIT_PATTERN, expected_brewery)
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

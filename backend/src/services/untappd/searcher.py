"""
Untappd search orchestration.
Coordinates text_utils, validators, and http_client to find beer URLs on Untappd.
"""
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Optional, TypedDict, List

import requests
from bs4 import BeautifulSoup

from .text_utils import (
    clean_beer_name, clean_brewery_name, strip_beer_suffix,
    normalize_for_comparison, COMMON_SUFFIXES
)
from .validators import validate_beer_match, validate_brewery_match, set_brewery_aliases
from .http_client import (
    search_brewery_beer, scrape_beer_details, scrape_brewery_details, search_brewery
)

logger = logging.getLogger(__name__)

# ── TypedDicts ────────────────────────────────────────────────────────────────

class UntappdBeerDetails(TypedDict, total=False):
    untappd_beer_name: str
    untappd_brewery_name: str
    untappd_brewery_url: str
    untappd_style: str
    untappd_abv: str
    untappd_ibu: str
    untappd_rating: str
    untappd_rating_count: str
    untappd_label: str
    untappd_fetched_at: str


class UntappdBreweryDetails(TypedDict, total=False):
    brewery_name: str
    location: str
    brewery_type: str
    website: str
    logo_url: str
    stats: dict
    fetched_at: str


class UntappdSearchResult(TypedDict, total=False):
    url: Optional[str]
    success: bool
    failure_reason: Optional[str]
    error_message: Optional[str]


# ── Brewery aliases ───────────────────────────────────────────────────────────

def _load_brewery_aliases() -> dict:
    """Load brewery aliases from aliases.json."""
    aliases_path = Path(__file__).parent / "aliases.json"
    try:
        with open(aliases_path, encoding="utf-8") as f:
            aliases = json.load(f)
        logger.debug(f"Loaded {len(aliases)} brewery aliases from aliases.json")
        return aliases
    except Exception as e:
        logger.warning(f"Could not load aliases.json: {e}")
        return {}


BREWERY_ALIASES = _load_brewery_aliases()
set_brewery_aliases(BREWERY_ALIASES)  # Inject into validators module


# ── Main search function ──────────────────────────────────────────────────────

def get_untappd_url(
    brewery_name: str,
    beer_name: str,
    beer_name_jp: str = None,
    brewery_url: str = None,
    search_hint: str = None,
    beer_name_core: str = None,
) -> UntappdSearchResult:
    """
    Searches for an Untappd beer page using direct scraping of Untappd.com.

    Search priority:
      0. Gemini-generated search_hint (fastest, most accurate)
      1. Within known brewery page (brewery_url provided)
      2. beer_name + brewery_name combinations
      3. beer_name only (with brewery validation)
      4. Stripped style suffix fallbacks
      5. Edition/Anniversary removal fallback
      6. Japanese name fallback
      7. Year/vintage removal fallback
      8. Brewery-specific fallback (find brewery URL first)

    Args:
        brewery_name: Name of the brewery (prefer English).
        beer_name: Name of the beer (prefer English).
        beer_name_jp: Japanese beer name (optional fallback).
        brewery_url: Known Untappd URL of the brewery (priority search).
        search_hint: Gemini-generated short search query (e.g. "Realm's Remedy Holy Mountain").
        beer_name_core: Core beer name without edition qualifiers (e.g. "Realm's Remedy").

    Returns:
        UntappdSearchResult with url, success, failure_reason, error_message.
    """
    if not brewery_name and not beer_name and not beer_name_jp:
        return {
            'url': None,
            'success': False,
            'failure_reason': 'missing_info',
            'error_message': 'No brewery or beer name provided'
        }

    def _search(query: str, validate_brewery: str = None, validate_beer: str = None) -> Optional[str]:
        """Single Untappd search attempt with optional validation."""
        normalized_query = re.sub(r'\s*-\s*', ' ', query).strip()
        if normalized_query != query:
            logger.info(f"Normalized query hyphens: '{query}' -> '{normalized_query}'")
        encoded_query = urllib.parse.quote(normalized_query)
        url = f"https://untappd.com/search?q={encoded_query}"
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                for res in soup.select('.beer-item')[:3]:
                    name_tag = res.select_one('.name a')
                    if name_tag:
                        href = name_tag.get('href')
                        if href and "/b/" in href:
                            if validate_brewery and not validate_brewery_match(res, validate_brewery):
                                continue
                            if validate_beer and not validate_beer_match(res, validate_beer):
                                continue
                            return f"https://untappd.com{href}"
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}")
            raise
        return None

    def _found(url: str) -> UntappdSearchResult:
        return {'url': url, 'success': True, 'failure_reason': None, 'error_message': None}

    try:
        # ── PRIORITY 0: Gemini search_hint ───────────────────────────────────
        if search_hint:
            logger.info(f"PRIORITY 0: Using Gemini search_hint: '{search_hint}'")
            r = _search(search_hint, validate_brewery=brewery_name, validate_beer=beer_name_core or beer_name)
            if r:
                logger.info(f"Found (search_hint): {r}")
                return _found(r)

        # ── PRIORITY 1: Within known brewery page ─────────────────────────────
        if brewery_url and (beer_name or beer_name_jp):
            logger.info(f"PRIORITY 1: Brewery-specific search (URL: {brewery_url})")
            q_base = beer_name or beer_name_jp
            if brewery_name and brewery_name.lower() in q_base.lower():
                q_base = q_base.replace(brewery_name, "").strip()
            q_stripped = strip_beer_suffix(q_base) or q_base
            b_queries = [q_base, q_stripped]
            if beer_name_core and beer_name_core not in b_queries:
                b_queries.append(beer_name_core)
            for q in b_queries:
                if not q:
                    continue
                logger.info(f"Searching within brewery page: {q}")
                r = search_brewery_beer(brewery_url, q, validate_beer_fn=validate_beer_match, validate_beer=beer_name or beer_name_jp)
                if r:
                    logger.info(f"Found (brewery page): {r}")
                    return _found(r)

        # ── PRIORITY 2: beer_name + brewery_name combinations ─────────────────
        if beer_name:
            queries = []

            def _add_brewery_queries(b_name):
                resolved = BREWERY_ALIASES.get(b_name, [b_name])[0] if b_name in BREWERY_ALIASES else b_name
                if resolved:
                    queries.append(f"{resolved} {beer_name}")
                    queries.append(f"{beer_name} {resolved}")

            _add_brewery_queries(brewery_name)
            cleaned_b = clean_brewery_name(brewery_name)
            if cleaned_b != brewery_name:
                _add_brewery_queries(cleaned_b)

            # Collaboration breweries
            if brewery_name and any(sep in brewery_name for sep in [' x ', 'x ', '×', '/']):
                for part in re.split(r'\s*[x×/]\s*', brewery_name):
                    p = part.strip()
                    if p:
                        _add_brewery_queries(p)
                        cp = clean_brewery_name(p)
                        if cp != p:
                            _add_brewery_queries(cp)

            for search_query in queries:
                logger.info(f"Searching: {search_query}")
                r = _search(search_query, validate_brewery=brewery_name, validate_beer=beer_name)
                if r:
                    logger.info(f"Found: {r}")
                    return _found(r)

        # ── PRIORITY 3: beer_name only (with brewery validation) ──────────────
        if beer_name and brewery_name:
            logger.info(f"Fallback (beer name only): {beer_name}")
            r = _search(beer_name, validate_brewery=brewery_name, validate_beer=beer_name)
            if r:
                logger.info(f"Found (beer-only): {r}")
                return _found(r)

        # ── PRIORITY 4: Strip style suffix ────────────────────────────────────
        if beer_name:
            stripped = strip_beer_suffix(beer_name)
            if stripped:
                cleaned_stripped = clean_beer_name(stripped)
                for q in [
                    f"{cleaned_stripped} {brewery_name}" if brewery_name else cleaned_stripped,
                    cleaned_stripped,
                ]:
                    logger.info(f"Retrying (suffix stripped): {q}")
                    r = _search(q, validate_brewery=brewery_name)
                    if r:
                        logger.info(f"Found (stripped): {r}")
                        return _found(r)

        # ── PRIORITY 5: Edition/Anniversary removal ───────────────────────────
        if beer_name:
            core = re.sub(
                r'\s+(?:\d+(?:st|nd|rd|th)\s+)?(?:Anniversary|Edition|Release|Collaboration|Collab|Special|Limited|Reserve|Barrel[\s-]Aged)\b.*$',
                '', beer_name, flags=re.IGNORECASE
            ).strip()
            core = re.sub(
                r'\s+(?:IPA|DIPA|TIPA|Pale Ale|Stout|Lager|Saison|Porter|Ale|Sour|Gose)\s*$',
                '', core, flags=re.IGNORECASE
            ).strip()
            if core and core != beer_name and len(core) >= 4:
                logger.info(f"Edition removal: '{beer_name}' -> '{core}'")
                q = f"{core} {brewery_name}" if brewery_name else core
                r = _search(q, validate_brewery=brewery_name, validate_beer=core)
                if r:
                    logger.info(f"Found (edition removal): {r}")
                    return _found(r)

        # ── PRIORITY 6: Japanese name fallback ───────────────────────────────
        if beer_name_jp:
            cleaned_jp = clean_beer_name(beer_name_jp)
            jp_queries = []
            if cleaned_jp and cleaned_jp != beer_name_jp:
                jp_queries.append((f"{cleaned_jp} {brewery_name}" if brewery_name else cleaned_jp, cleaned_jp))
            jp_queries.append((beer_name_jp, beer_name_jp))
            for q, validate in jp_queries:
                logger.info(f"Retrying (Japanese): {q}")
                r = _search(q, validate_brewery=brewery_name, validate_beer=validate)
                if r:
                    logger.info(f"Found (JP name): {r}")
                    return _found(r)

        # ── PRIORITY 7: Year/vintage removal ─────────────────────────────────
        if beer_name and re.search(r'\b20[2-9]\d\b', beer_name):
            no_year = re.sub(r'\s*\b20[2-9]\d\b\s*', ' ', beer_name).strip()
            no_year = ' '.join(no_year.split())
            if no_year and no_year != beer_name:
                logger.info(f"Retrying (no year): {no_year}")
                for q in [f"{no_year} {brewery_name}" if brewery_name else no_year, no_year]:
                    r = _search(q, validate_brewery=brewery_name)
                    if r:
                        logger.info(f"Found (no year): {r}")
                        return _found(r)

        # ── PRIORITY 8: Find brewery URL, search within it ────────────────────
        if brewery_name and (beer_name or beer_name_jp) and not brewery_url:
            logger.info(f"Trying brewery-specific search for: {brewery_name}")
            b_url = search_brewery(brewery_name)
            if b_url:
                q_base = beer_name or beer_name_jp
                if brewery_name.lower() in q_base.lower():
                    q_base = q_base.replace(brewery_name, "").strip()
                q_stripped = strip_beer_suffix(q_base) or q_base
                for q in [q_base, q_stripped]:
                    if not q:
                        continue
                    logger.info(f"Searching within brewery page: {q}")
                    r = search_brewery_beer(b_url, q, validate_beer_fn=validate_beer_match, validate_beer=beer_name or beer_name_jp)
                    if r:
                        logger.info(f"Found (brewery fallback): {r}")
                        return _found(r)

        # ── All strategies exhausted ──────────────────────────────────────────
        final_q = clean_beer_name(f"{beer_name or beer_name_jp or ''} {brewery_name or ''}".strip()) or ""
        fallback_url = f"https://untappd.com/search?q={urllib.parse.quote(final_q)}"
        logger.info("No direct link found. Returning search URL as failure.")
        return {
            'url': fallback_url,
            'success': False,
            'failure_reason': 'no_results',
            'error_message': f'No direct beer page found after all search strategies for: {final_q}'
        }

    except Exception as e:
        logger.error(f"Network error during Untappd search: {e}")
        return {
            'url': None,
            'success': False,
            'failure_reason': 'network_error',
            'error_message': str(e)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    print(scrape_beer_details(test_url))

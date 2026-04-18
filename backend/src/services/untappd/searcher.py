"""
Untappd search orchestration.
Coordinates text_utils, validators, and http_client to find beer URLs on Untappd.
"""
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any, cast

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
from ...core.types import UntappdBeerDetails, UntappdBreweryDetails, UntappdSearchResult

logger = logging.getLogger(__name__)


# ── Brewery aliases ───────────────────────────────────────────────────────────

def _load_brewery_aliases() -> Dict[str, List[str]]:
    """Load brewery aliases from aliases.json."""
    aliases_path: Path = Path(__file__).parent / "aliases.json"
    try:
        with open(aliases_path, encoding="utf-8") as f:
            aliases: Dict[str, List[str]] = json.load(f)
        logger.debug(f"Loaded {len(aliases)} brewery aliases from aliases.json")
        return aliases
    except Exception as e:
        logger.warning(f"Could not load aliases.json: {e}")
        return {}


BREWERY_ALIASES: Dict[str, List[str]] = _load_brewery_aliases()
set_brewery_aliases(BREWERY_ALIASES)  # Inject into validators module


# ── Main search function ──────────────────────────────────────────────────────

def get_untappd_url(
    brewery_name: str,
    beer_name: str,
    beer_name_jp: Optional[str] = None,
    brewery_url: Optional[str] = None,
    search_hint: Optional[str] = None,
    beer_name_core: Optional[str] = None,
) -> UntappdSearchResult:
    """
    Searches for an Untappd beer page with a multi-stage strategy:
    1. If brewery_url is provided or found, search WITHIN that brewery's beer list.
    2. Fallback to DuckDuckGo search if brewery-specific search fails.
    """
    if not brewery_name and not beer_name and not beer_name_jp:
        return {
            'url': None,
            'success': False,
            'failure_reason': 'missing_info',
            'error_message': 'No brewery or beer name provided'
        }

    target_beer_name: str = beer_name_core or beer_name or beer_name_jp or ""
    u_brewery_url: Optional[str] = brewery_url

    # --- Stage 1: Identify Brewery URL if not provided ---
    if not u_brewery_url and brewery_name:
        logger.info(f"Brewery URL missing. Searching for brewery: '{brewery_name}'")
        u_brewery_url = search_brewery(brewery_name)
        if u_brewery_url:
            logger.info(f" Brewery found: {u_brewery_url}")

    # --- Stage 2: Search WITHIN Brewery ---
    if u_brewery_url:
        logger.info(f"Searching for '{target_beer_name}' within brewery: {u_brewery_url}")
        found_url: Optional[str] = search_brewery_beer(
            u_brewery_url, 
            target_beer_name, 
            validate_beer_fn=validate_beer_match,
            validate_beer=target_beer_name
        )
        if found_url:
            logger.info(f" Beer found via brewery search: {found_url}")
            return {
                'url': found_url,
                'success': True,
                'failure_reason': None,
                'error_message': None
            }
        logger.info(" Brewery-specific search returned no verified matches.")

    # --- Stage 3: Fallback to DuckDuckGo ---
    query: str
    if search_hint:
        query = f"untappd {search_hint}"
    else:
        query = f"untappd {brewery_name} {target_beer_name}".strip()

    logger.info(f"Falling back to DuckDuckGo search for: '{query}'")

    try:
        from ddgs import DDGS
        from .text_utils import normalize_for_comparison, strip_for_core_comparison

        def title_is_valid(title: str, exp_brewery: str, exp_beer: str) -> bool:
            t_norm: str = normalize_for_comparison(title)
            
            # Check brewery
            if exp_brewery:
                b_norm: str = normalize_for_comparison(exp_brewery)
                if b_norm not in t_norm:
                    # check aliases
                    if BREWERY_ALIASES:
                        for alias in BREWERY_ALIASES.get(exp_brewery, []):
                            if normalize_for_comparison(alias) in t_norm:
                                return True
                    return False
                    
            # Check beer
            if exp_beer:
                beer_core: str = normalize_for_comparison(strip_for_core_comparison(exp_beer))
                if beer_core and beer_core not in t_norm:
                    if beer_name_jp and normalize_for_comparison(beer_name_jp) in t_norm:
                        pass
                    else:
                        return False
            return True

        with DDGS() as ddgs:
            results: Any = ddgs.text(query, max_results=5)
            
            for res in results:
                href: str = res.get("href", "")
                title: str = res.get("title", "")
                
                if "untappd.com/b/" in href:
                    if title_is_valid(title, brewery_name, target_beer_name):
                        logger.info(f" Found via DuckDuckGo: {href}")
                        return {
                            'url': href,
                            'success': True,
                            'failure_reason': None,
                            'error_message': None
                        }
                    else:
                        logger.debug(f" DDG result failed validation: {title}")
                    
        # Fallback if no result
        fallback_url: str = f"https://untappd.com/search?q={urllib.parse.quote(query.replace('untappd ', ''))}"
        logger.info(f"No direct link found. Returning search URL as failure.")
        return {
            'url': fallback_url,
            'success': False,
            'failure_reason': 'no_results',
            'error_message': f'No direct beer page found for: {query}'
        }

    except Exception as e:
        logger.error(f"Error during DuckDuckGo search: {e}")
        return {
            'url': None,
            'success': False,
            'failure_reason': 'network_error',
            'error_message': str(e)
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_url: str = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    print(scrape_beer_details(test_url))

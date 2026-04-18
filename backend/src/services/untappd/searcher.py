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
    Searches for an Untappd beer page using DuckDuckGo search.
    Expects brewery classification to have already been done, ensuring high accuracy.
    """
    if not brewery_name and not beer_name and not beer_name_jp:
        return {
            'url': None,
            'success': False,
            'failure_reason': 'missing_info',
            'error_message': 'No brewery or beer name provided'
        }

    # Construct search query
    if search_hint:
        query = f"untappd {search_hint}"
    else:
        base_beer = beer_name_core or beer_name or beer_name_jp or ""
        base_brewery = brewery_name or ""
        query = f"untappd {base_brewery} {base_beer}".strip()

    logger.info(f"Searching DuckDuckGo for: '{query}'")

    try:
        from ddgs import DDGS
        import urllib.parse
        from .text_utils import normalize_for_comparison, strip_for_core_comparison

        def title_is_valid(title: str, exp_brewery: str, exp_beer: str) -> bool:
            t_norm = normalize_for_comparison(title)
            
            # Check brewery
            if exp_brewery:
                b_norm = normalize_for_comparison(exp_brewery)
                if b_norm not in t_norm:
                    # Allow fuzzy match if alias or collab, but let's be strict for now
                    return False
                    
            # Check beer
            if exp_beer:
                beer_core = normalize_for_comparison(strip_for_core_comparison(exp_beer))
                if beer_core and beer_core not in t_norm:
                    # Allow some looseness if Japanese is present
                    if beer_name_jp and normalize_for_comparison(beer_name_jp) in t_norm:
                        pass
                    else:
                        return False
            return True

        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
            
            for res in results:
                href = res.get("href", "")
                title = res.get("title", "")
                
                # Check if it's a valid Untappd beer URL
                if "untappd.com/b/" in href:
                    if title_is_valid(title, brewery_name, beer_name_core or beer_name):
                        logger.info(f"Found via DuckDuckGo: {href}")
                        return {
                            'url': href,
                            'success': True,
                            'failure_reason': None,
                            'error_message': None
                        }
                    else:
                        logger.debug(f"DDG result failed validation: {title}")
                    
        # Fallback if no result
        fallback_url = f"https://untappd.com/search?q={urllib.parse.quote(query.replace('untappd ', ''))}"
        logger.info(f"No direct link found via DDG. Returning search URL as failure.")
        return {
            'url': fallback_url,
            'success': False,
            'failure_reason': 'no_results',
            'error_message': f'No direct beer page found via DuckDuckGo for: {query}'
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
    test_url = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    print(scrape_beer_details(test_url))

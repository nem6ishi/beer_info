"""
Untappd search orchestration.
Coordinates text_utils, validators, and http_client to find beer URLs on Untappd.
"""
import asyncio
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict, Any


from .text_utils import (
    normalize_for_comparison, strip_for_core_comparison,
    normalize_singular_plural,
    has_variant_mismatch, COLLAB_SPLIT_PATTERN,
    clean_brewery_name
)
from .validators import validate_beer_match, score_beer_match, set_brewery_aliases
from .http_client import (
    search_brewery_beer, scrape_beer_details, search_brewery
)
from ...core.types import UntappdSearchResult

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

async def get_untappd_url(
    brewery_name: str,
    beer_name: str,
    beer_name_jp: Optional[str] = None,
    brewery_url: Optional[str] = None,
    search_hint: Optional[str] = None,
    beer_name_core: Optional[str] = None,
) -> UntappdSearchResult:
    """
    Searches for an Untappd beer page with a multi-stage strategy.
    Implements a two-pass search for year-labeled beers:
    1. Try with the year (e.g., "The Gateway 2026")
    2. If no results, fallback to searching without the year ("The Gateway").
    """
    # 1. まず元のクエリ（西暦あり）で検索
    result = await _get_untappd_url_single(
        brewery_name=brewery_name,
        beer_name=beer_name,
        beer_name_jp=beer_name_jp,
        brewery_url=brewery_url,
        search_hint=search_hint,
        beer_name_core=beer_name_core
    )
    
    if result.get('success'):
        return result
        
    # 2. 失敗した場合、西暦（20XX）が含まれているかチェックしてフォールバック
    has_year = False
    for text in [beer_name_core, beer_name, search_hint]:
        if text and re.search(r'\b20\d{2}\b', text):
            has_year = True
            break
            
    if has_year and result.get('failure_reason') == 'no_results':
        logger.info("🔄 [Year-fallback] 'With-year' search failed. Retrying WITHOUT year...")
        
        def remove_year(t: Optional[str]) -> Optional[str]:
            if not t:
                return t
            cleaned = re.sub(r'\b20\d{2}\b', '', t).strip()
            return ' '.join(cleaned.split()) if cleaned else None

        no_year_beer_name = remove_year(beer_name) or ""
        no_year_beer_name_core = remove_year(beer_name_core)
        no_year_search_hint = remove_year(search_hint)
        
        logger.info(f"🔄 [Year-fallback] Alternative names: Beer='{no_year_beer_name}', Core='{no_year_beer_name_core}', Hint='{no_year_search_hint}'")
        
        retry_result = await _get_untappd_url_single(
            brewery_name=brewery_name,
            beer_name=no_year_beer_name,
            beer_name_jp=beer_name_jp,
            brewery_url=brewery_url,
            search_hint=no_year_search_hint,
            beer_name_core=no_year_beer_name_core
        )
        if retry_result.get('success'):
            logger.info("✅ [Year-fallback] Found match without year!")
            return retry_result
            
    return result


async def _get_untappd_url_single(
    brewery_name: str,
    beer_name: str,
    beer_name_jp: Optional[str] = None,
    brewery_url: Optional[str] = None,
    search_hint: Optional[str] = None,
    beer_name_core: Optional[str] = None,
) -> UntappdSearchResult:
    """
    Core search logic for a single pass.
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
    primary_brewery_search = re.split(COLLAB_SPLIT_PATTERN, brewery_name)[0] if brewery_name else ""
    shop_names = {'choseiya', 'ちょうせいや', 'arome', 'アローム', 'beervolta', 'beer volta', 'maruho', 'maruho saketen', 'マルホ酒店', '151l', '一期一会～る', 'antenna america', 'アンテナアメリカ'}

    candidate_brewery_urls: List[str] = [u_brewery_url] if u_brewery_url else []

    if not candidate_brewery_urls and primary_brewery_search and primary_brewery_search.strip().lower() not in shop_names:
        try:
            from backend.src.services.store.brewery_manager import BreweryManager
            bm = BreweryManager()
            bm_found = bm.find_breweries_in_text(primary_brewery_search) or bm.find_breweries_in_text(brewery_name)
            if bm_found:
                for bf in bm_found:
                    if bf.get("untappd_url") and bf.get("untappd_url") not in candidate_brewery_urls:
                        candidate_brewery_urls.append(bf.get("untappd_url"))
                        logger.info(f"  [BreweryManager] Found candidate brewery URL in cache: {bf.get('untappd_url')}")
        except Exception as e:
            logger.debug(f"BreweryManager check failed: {e}")

        if not candidate_brewery_urls:
            aliases_to_try = [primary_brewery_search]
            if primary_brewery_search in BREWERY_ALIASES:
                aliases_to_try.extend(BREWERY_ALIASES[primary_brewery_search])
            for b_query in aliases_to_try:
                logger.info(f"Brewery URL missing. Searching for brewery: '{b_query}'")
                b_found_url = await search_brewery(b_query)
                if b_found_url and b_found_url not in candidate_brewery_urls:
                    logger.info(f" Brewery found: {b_found_url}")
                    candidate_brewery_urls.append(b_found_url)
                    break

    # --- Stage 2: Search WITHIN Brewery ---
    found_url: Optional[str] = None
    for cand_b_url in candidate_brewery_urls:
        logger.info(f"Searching for '{target_beer_name}' within brewery: {cand_b_url}")
        found_url = await search_brewery_beer(
            cand_b_url, 
            target_beer_name, 
            validate_beer_fn=validate_beer_match,
            validate_beer=target_beer_name,
            score_beer_fn=score_beer_match,
            validate_brewery=brewery_name,
        )
        if not found_url and beer_name_jp and beer_name_jp != target_beer_name:
            logger.info(f"🔄 [JP-fallback] Searching for Japanese name '{beer_name_jp}' within brewery: {cand_b_url}")
            found_url = await search_brewery_beer(
                cand_b_url,
                beer_name_jp,
                validate_beer_fn=validate_beer_match,
                validate_beer=beer_name_jp,
                score_beer_fn=score_beer_match,
                validate_brewery=brewery_name,
            )
        if not found_url:
            tokens = []
            for text in [target_beer_name, beer_name_jp]:
                if not text:
                    continue
                words = re.split(r'[\s/—–\-([（）\])]+', text)
                for w in reversed(words):
                    w_clean = w.strip()
                    if len(w_clean) < 2 or (w_clean.isascii() and len(w_clean) < 3):
                        continue
                    if w_clean.lower() in {'ipa', 'dipa', 'tipa', 'neipa', 'ale', 'stout', 'lager', 'pilsner', 'sour', 'porter', 'saison', 'gose', 'hazy', 'double', 'triple', 'single', 'imperial', 'session', 'fruited', 'wild', 'beer', 'cider', 'mead', '330ml', '350ml', '500ml', '750ml'}:
                        continue
                    if w_clean not in tokens and w_clean != target_beer_name and w_clean != beer_name_jp:
                        tokens.append(w_clean)
            for token in tokens[:4]:
                logger.info(f"🔄 [Token-fallback] Searching for token '{token}' within brewery: {cand_b_url}")
                found_url = await search_brewery_beer(
                    cand_b_url,
                    token,
                    validate_beer_fn=validate_beer_match,
                    validate_beer=target_beer_name,
                    score_beer_fn=score_beer_match,
                    validate_brewery=brewery_name,
                )
                if found_url:
                    logger.info(f" Beer found via token fallback search ('{token}'): {found_url}")
                    break
        if found_url:
            logger.info(f" Beer found via brewery search: {found_url}")
            return {
                'url': found_url,
                'success': True,
                'failure_reason': None,
                'error_message': None
            }
    if candidate_brewery_urls:
        logger.info(" Brewery-specific search returned no verified matches.")

    # --- Stage 3: Fallback to DuckDuckGo ---
    query: str
    if search_hint:
        query = f"untappd {search_hint}"
    else:
        query = f"untappd {primary_brewery_search} {target_beer_name}".strip()

    logger.info(f"Falling back to DuckDuckGo search for: '{query}'")

    try:
        from ddgs import DDGS

        def title_is_valid(title: str, exp_brewery: str, exp_beer: str) -> bool:
            t_norm: str = normalize_for_comparison(title)
            
            # Check brewery
            if exp_brewery:
                primary_breweries = re.split(COLLAB_SPLIT_PATTERN, exp_brewery)
                brewery_match = False
                for p_brew in primary_breweries:
                    b_norm: str = normalize_for_comparison(clean_brewery_name(p_brew))
                    if b_norm and b_norm in t_norm:
                        brewery_match = True
                        break
                    # check aliases
                    if BREWERY_ALIASES:
                        for alias in BREWERY_ALIASES.get(p_brew, []):
                            if normalize_for_comparison(alias) in t_norm:
                                brewery_match = True
                                break
                    if brewery_match:
                        break
                
                if not brewery_match:
                    return False
                    
            # Check beer
            if exp_beer:
                beer_core: str = normalize_for_comparison(strip_for_core_comparison(exp_beer))
                beer_core_pl: str = normalize_for_comparison(strip_for_core_comparison(normalize_singular_plural(exp_beer)))
                t_norm_pl: str = normalize_for_comparison(normalize_singular_plural(title))
                if beer_core and beer_core not in t_norm and beer_core_pl not in t_norm_pl:
                    if beer_name_jp and normalize_for_comparison(beer_name_jp) in t_norm:
                        pass
                    else:
                        return False
                # Check for variant modifier mismatch in the title
                if has_variant_mismatch(title, exp_beer):
                    logger.debug(f"  [DDG] Variant mismatch in title: '{title}' vs '{exp_beer}'")
                    return False
            return True

        max_retries = 3
        for attempt in range(max_retries):
            try:
                def _do_ddg_search():
                    with DDGS(timeout=10) as ddgs:
                        res = ddgs.text(query, max_results=5)
                        return list(res) if res else []
                        
                results: Any = await asyncio.to_thread(_do_ddg_search)
                    
                if not results:
                    results = []
                        
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
                    
                # If we finish the loop without returning, it means we either got 0 results or none validated.
                # This is a normal failure, not a rate limit exception, so break and fallback.
                break
            except Exception as inner_e:
                error_str = str(inner_e).lower()
                if "rate limit" in error_str or "202" in error_str or "timeout" in error_str or "ratelimit" in error_str:
                    wait_time = 15 * (attempt + 1)
                    logger.warning(f"  [DDG] Rate limit or timeout hit. Sleeping for {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    if attempt == max_retries - 1:
                        raise inner_e
                else:
                    raise inner_e
                    
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
    import asyncio
    logging.basicConfig(level=logging.INFO)
    test_url: str = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    print(asyncio.run(scrape_beer_details(test_url)))

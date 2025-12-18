import logging
import urllib.parse
from datetime import datetime
from typing import Optional, TypedDict, List
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class UntappdBeerDetails(TypedDict, total=False):
    untappd_beer_name: str
    untappd_brewery_name: str
    untappd_brewery_url: str # New field
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
    stats: dict # {total, unique, monthly, ratings}
    fetched_at: str


BREWERY_ALIASES = {
    "鬼伝説": ["Wakasaimo"],
    "Oni Densetsu": ["Wakasaimo"],
    "ヨロッコ": ["Yorocco Beer"],
    "Shiga Kogen": ["Tamamura Honten"],
    "Shiga Kogen Beer": ["Tamamura Honten"],
    "志賀高原": ["Tamamura Honten"],
    "CRAFT ROCK": ["CRAFTROCK"],
    "CRAFT ROCK Brewing": ["CRAFTROCK Brewing"],
    "麦雑穀工房": ["Zakkoku Koubou Microbrewery"],
}

COMMON_SUFFIXES = [
    " IPA", " Hazy IPA", " Double IPA", " DIPA", " Triple IPA", " TIPA", " NEIPA", " West Coast IPA", " Session IPA", " DDH IPA", " TDH IPA",
    " Pale Ale", " Stout", " Imperial Stout", " Lager", " Pilsner", " Sour", 
    " Gose", " Porter", " Ale", " Wheat", " Saison", " Barleywine", " Lambic", " Gueuze", " Fruit Beer"
]
# Sort by length desc to remove longest match first
COMMON_SUFFIXES.sort(key=len, reverse=True)

import re

def clean_beer_name(name: str) -> str:
    """
    Cleans beer name by removing common noise patterns:
    - Japanese series markers (〜, シリーズ, #XX, Vol.X)
    - Batch/version markers (Batch X, Ver.X, 2024, etc.)
    - Special characters and brackets with content
    """
    if not name:
        return name
    
    original = name
    
    # Remove content after 〜 (wave dash - usually series info)
    name = re.sub(r'〜.*$', '', name)
    name = re.sub(r'~.*$', '', name)
    
    # Remove シリーズ and everything after
    name = re.sub(r'シリーズ.*$', '', name)
    
    # Remove #XX, Vol.X, Batch X patterns
    name = re.sub(r'#\d+', '', name)
    name = re.sub(r'Vol\.?\s*\d+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'Batch\s*\d+', '', name, flags=re.IGNORECASE)
    
    # Remove year patterns at the end (2024, 2025)
    name = re.sub(r'\s+20\d{2}\s*$', '', name)
    
    # Remove Japanese parentheses content that looks like version info
    name = re.sub(r'（[^）]*版[^）]*）', '', name)
    
    # Remove -〇〇編- style suffixes (e.g., -ラガー編-, -IPA編-)
    name = re.sub(r'-[^-]+編-?$', '', name)
    name = re.sub(r'－[^－]+編－?$', '', name)  # Full-width dash
    
    # Clean up extra whitespace
    name = ' '.join(name.split())
    
    if name != original:
        logger.info(f"Cleaned beer name: '{original}' -> '{name}'")
    
    return name.strip()

def strip_beer_suffix(beer_name: str) -> Optional[str]:
    """
    Strips common beer style suffixes from the beer name.
    Returns the stripped name if a suffix was found, otherwise None.
    """
    lower_name = beer_name.lower()
    for suffix in COMMON_SUFFIXES:
        if lower_name.endswith(suffix.lower()):
            stripped = beer_name[:-len(suffix)].strip()
            logger.info(f"Detected suffix '{suffix}'. Stripped to: '{stripped}'")
            return stripped
    return None

def normalize_for_comparison(text: str) -> str:
    """Removes whitespace and non-alphanumeric characters for fuzzy comparison."""
    if not text:
        return ""
    return "".join(c.lower() for c in text if c.isalnum())

def validate_brewery_match(result_element: BeautifulSoup, expected_brewery: str) -> bool:
    """
    Checks if the brewery name in the search result matches the expected brewery.
    Uses normalized comparison (ignoring spaces/punctuation) and aliases.
    """
    if not expected_brewery:
        return True 
        
    brewery_tag = result_element.select_one('.brewery')
    if not brewery_tag:
        return False
        
    result_brewery = brewery_tag.get_text(strip=True)
    
    # 1. Normalization Check
    rb_norm = normalize_for_comparison(result_brewery)
    eb_norm = normalize_for_comparison(expected_brewery)
    
    if rb_norm in eb_norm or eb_norm in rb_norm:
        return True
        
    # 2. Alias Check
    if expected_brewery in BREWERY_ALIASES:
        for alias in BREWERY_ALIASES[expected_brewery]:
            alias_norm = normalize_for_comparison(alias)
            if alias_norm in rb_norm:
                return True

    logger.debug(f"Validation failed: Result '{result_brewery}' ({rb_norm}) != Expected '{expected_brewery}' ({eb_norm})")
    return False

def get_untappd_url(brewery_name: str, beer_name: str, beer_name_jp: str = None) -> Optional[str]:
    """
    Searches for an Untappd beer page using direct scraping of Untappd.com.
    
    Args:
        brewery_name (str): Name of the brewery (prefer English).
        beer_name (str): Name of the beer (prefer English).
        beer_name_jp (str): Name of the beer in Japanese (optional fallback).
        
    Returns:
        Optional[str]: A direct beer page URL if found, otherwise the search result page URL.
    """
    if not brewery_name and not beer_name and not beer_name_jp:
        return None

    def search_untappd(query: str, validate_brewery: str = None) -> Optional[str]:
        """Helper to perform a single search attempt."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://untappd.com/search?q={encoded_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'lxml')
                results = soup.select('.beer-item')
                
                # Check top 3 results
                for res in results[:3]:
                    name_tag = res.select_one('.name a')
                    if name_tag:
                        href = name_tag.get('href')
                        if href and "/b/" in href:
                            if validate_brewery:
                                if validate_brewery_match(res, validate_brewery):
                                    return f"https://untappd.com{href}"
                            else:
                                return f"https://untappd.com{href}"
                                
        except Exception as e:
            logger.error(f"Search error for '{query}': {e}")
        
        return None

    # Primary Search: beer_name + brewery_name (or alias)
    if beer_name:
        parts = []
        parts.append(beer_name)
        
        search_brewery_name = brewery_name
        if brewery_name and brewery_name in BREWERY_ALIASES:
            # Use the first alias (English) for better search results
            search_brewery_name = BREWERY_ALIASES[brewery_name][0]
            logger.info(f"Using alias for search: {brewery_name} -> {search_brewery_name}")
            
        if search_brewery_name: parts.append(search_brewery_name)
        
        search_query = " ".join(parts)
        logger.info(f"Searching: {search_query}")
        
        # We pass brewery_name for validation since we are explicitly searching for it
        result = search_untappd(search_query, validate_brewery=brewery_name)
        if result:
            logger.info(f"Found direct link: {result}")
            return result
    
    # Fallback Search: beer_name only
    # Only do this if we actually have a brewery name to validate against, 
    # otherwise searching for just "Pale Ale" is useless.
    if beer_name and brewery_name:
        logger.info(f"Fallback search (Beer Name Only): {beer_name}")
        # CRITICAL: Must validate brewery here, otherwise we get random matching beer
        result = search_untappd(beer_name, validate_brewery=brewery_name)
        if result:
            logger.info(f"Found direct link (fallback): {result}")
            return result
            
    # Advanced Fallback: Strip common style suffixes
    if beer_name:
        stripped_name = strip_beer_suffix(beer_name)
        if stripped_name:
            # Try 1: {Stripped} {Brewery}
            query = f"{stripped_name} {brewery_name}" if brewery_name else stripped_name
            logger.info(f"Retrying with stripped name: {query}")
            result = search_untappd(query, validate_brewery=brewery_name)
            if result:
                logger.info(f"Found direct link (stripped+brewery): {result}")
                return result
                
            # Try 2: {Stripped} only (with validation)
            if brewery_name:
                logger.info(f"Retrying with stripped name only: {stripped_name}")
                result = search_untappd(stripped_name, validate_brewery=brewery_name)
                if result:
                    logger.info(f"Found direct link (stripped only): {result}")
                    return result

    # Japanese Name Fallback
    if beer_name_jp:
        # Clean the Japanese name before searching
        cleaned_jp_name = clean_beer_name(beer_name_jp)
        
        # Try with cleaned name first
        if cleaned_jp_name and cleaned_jp_name != beer_name_jp:
            search_query_jp = f"{cleaned_jp_name} {brewery_name}" if brewery_name else cleaned_jp_name
            logger.info(f"Retrying with cleaned Japanese name: {search_query_jp}")
            result = search_untappd(search_query_jp, validate_brewery=brewery_name)
            if result:
                logger.info(f"Found direct link (cleaned JP name): {result}")
                return result
        
        # Try with original Japanese name
        logger.info(f"Retrying with Japanese name: {beer_name_jp}")
        result = search_untappd(beer_name_jp, validate_brewery=brewery_name)
        if result:
            logger.info(f"Found direct link (JP name): {result}")
            return result
            
    # Final Fallback: Return search URL
    final_query = search_query if search_query.strip() else (beer_name or beer_name_jp or "")
    # Also clean the final query
    final_query = clean_beer_name(final_query) or final_query
    encoded_query = urllib.parse.quote(final_query)
    fallback_url = f"https://untappd.com/search?q={encoded_query}"
    logger.info("No direct link found. Returning search URL.")
    return fallback_url


def scrape_beer_details(url: str) -> UntappdBeerDetails:
    """
    Scrapes detailed info from a specific Untappd beer URL.
    """
    details: UntappdBeerDetails = {}
    if not url or "untappd.com/b/" not in url:
        return details

    logger.info(f"Scraping details from: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Failed to load details. Status: {resp.status_code}")
            return details
            
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Name & Brewery
        name_tag = soup.select_one('.name h1')
        if name_tag: details['untappd_beer_name'] = name_tag.get_text(strip=True)
        
        brewery_tag = soup.select_one('.name .brewery')
        if brewery_tag: 
            # Prefer text from the link itself to avoid "Subsidiary of..." text
            brewery_link = brewery_tag.select_one('a')
            if brewery_link:
                details['untappd_brewery_name'] = brewery_link.get_text(strip=True)
            else:
                details['untappd_brewery_name'] = brewery_tag.get_text(strip=True)
            if brewery_link and brewery_link.get('href'):
                href = brewery_link.get('href')
                if href.startswith('/'):
                    details['untappd_brewery_url'] = f"https://untappd.com{href}"
                else:
                    details['untappd_brewery_url'] = href

        style_tag = soup.select_one('.name .style')
        if style_tag: details['untappd_style'] = style_tag.get_text(strip=True)
        
        # Label Image
        label_tag = soup.select_one('.label img')
        if label_tag and label_tag.has_attr('src'):
            details['untappd_label'] = label_tag['src']
        
        # Details Block (ABV, IBU, Rating, Count)
        abv_tag = soup.select_one('.details .abv')
        if abv_tag: 
            details['untappd_abv'] = abv_tag.get_text(strip=True).replace(' ABV', '')
            
        ibu_tag = soup.select_one('.details .ibu')
        if ibu_tag:
            details['untappd_ibu'] = ibu_tag.get_text(strip=True).replace(' IBU', '')
            
        rating_tag = soup.select_one('.details .num')
        if rating_tag:
            details['untappd_rating'] = rating_tag.get_text(strip=True).strip('()')
            
        raters_tag = soup.select_one('.details .raters')
        if raters_tag:
            count_text = raters_tag.get_text(strip=True)
            count_text = count_text.replace(' Ratings', '').replace(' Rating', '')
            count_text = count_text.strip('()')
            details['untappd_rating_count'] = count_text

        # Add timestamp
        details['untappd_fetched_at'] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"Detail scrape error: {e}")
        
    return details


def scrape_brewery_details(url: str) -> UntappdBreweryDetails:
    """
    Scrapes detailed info from a specific Untappd brewery URL.
    """
    details: UntappdBreweryDetails = {}
    if not url:
        return details
        
    logger.info(f"Scraping brewery details from: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Failed to load brewery details. Status: {resp.status_code}")
            return details
            
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Try finding the name directly (H1 is usually the name)
        name_tag = soup.select_one('h1')
        if name_tag:
            details['brewery_name'] = name_tag.get_text(strip=True)
            
            # The structure is usually:
            # <div class="basic">
            #   <h1>Wakasaimo Honpo</h1>
            #   <p class="brewery">Toyako, Hokkaido Japan</p>
            #   <p class="style">Micro Brewery</p>
            # </div>
            
            parent = name_tag.parent
            if parent:
                # Location often in a <p class="brewery"> or just <p>
                # Using class-agnostic p tag search based on position
                p_tags = parent.select('p')
                for p in p_tags:
                    text = p.get_text(strip=True)
                    # Skip subsidiary info
                    if "Subsidiary of" in text:
                        continue
                        
                    # Simple heuristic: If it looks like a location (Japan, US, etc) or has a map icon?
                    # Or relying on order: 1st is location, 2nd is type
                    # Untappd usually puts location first
                    if not details.get('location') and any(c.isalpha() for c in text): 
                         details['location'] = text
                    elif not details.get('brewery_type') and details.get('location') and text != details.get('location'):
                         details['brewery_type'] = text
        
        # Logo
        # .logo img is often the site header logo. The brewery logo is usually in div.label or div.basic
        logo_img = soup.select_one('.label img') or soup.select_one('.basic img') or soup.select_one('.logo img')
        if logo_img: details['logo_url'] = logo_img.get('src')
        
        # Website / Socials - usually in .social
        socials = soup.select('.social a')
        for link in socials:
            text = link.get_text(strip=True).lower()
            href = link.get('href')
            if 'website' in text or 'globe' in str(link): # sometimes icon
                details['website'] = href
        
        # Stats - usually in .stats
        stats_container = soup.select_one('.stats')
        if stats_container:
            stats = {}
            stat_items = stats_container.select('.item')
            for item in stat_items:
                label = item.select_one('.title')
                value = item.select_one('.count')
                if label and value:
                    l_text = label.get_text(strip=True).lower()
                    v_text = value.get_text(strip=True).replace(',', '')
                    if 'total' in l_text: stats['total_beers'] = v_text
                    elif 'unique' in l_text: stats['unique_users'] = v_text
                    elif 'monthly' in l_text: stats['monthly_checkins'] = v_text
                    elif 'ratings' in l_text: stats['rating_count'] = v_text
            details['stats'] = stats
            
        details['fetched_at'] = datetime.now().isoformat()
        
    except Exception as e:
        logger.error(f"Brewery scrape error: {e}")
        
    return details

def search_brewery(query: str) -> Optional[str]:
    """
    Searches for a brewery on Untappd and returns the brewery page URL.
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://untappd.com/search?q={encoded_query}&type=brewery"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'lxml')
            # Results are usually in .beer-item regardless of type, but struct differs
            # Brewery results: <div class="beer-item"> ... <p class="name"><a href="/w/brewery-name/123">Brewery Name</a></p>
            
            results = soup.select('.beer-item')
            for res in results[:1]: # Take first match
                name_tag = res.select_one('.name a')
                if name_tag:
                    href = name_tag.get('href')
                    # format: /w/slug/id OR /vanity_slug
                    if href and "/b/" not in href:
                         return f"https://untappd.com{href}"
                         
    except Exception as e:
        logger.error(f"Brewery search error for '{query}': {e}")
        
    return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Integration test
    test_url = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    # print(get_untappd_url("Inkhorn Brewing", "UGUISU"))
    print(scrape_beer_details(test_url))

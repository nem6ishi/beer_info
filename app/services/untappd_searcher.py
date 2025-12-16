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
    untappd_style: str
    untappd_abv: str
    untappd_ibu: str
    untappd_rating: str
    untappd_rating_count: str
    untappd_label: str
    untappd_fetched_at: str

COMMON_SUFFIXES = [
    " IPA", " Hazy IPA", " Double IPA", " DIPA", " Triple IPA", " TIPA", 
    " Pale Ale", " Stout", " Imperial Stout", " Lager", " Pilsner", " Sour", 
    " Gose", " Porter", " Ale", " Wheat", " Saison", " Barleywine"
]
# Sort by length desc to remove longest match first
COMMON_SUFFIXES.sort(key=len, reverse=True)

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

def validate_brewery_match(result_element: BeautifulSoup, expected_brewery: str) -> bool:
    """
    Checks if the brewery name in the search result matches the expected brewery.
    Uses a simple case-insensitive substring/inclusion check.
    """
    if not expected_brewery:
        return True # logic: if we don't know the brewery, we accept the result (legacy behavior or fallback)
        
    brewery_tag = result_element.select_one('.brewery')
    if not brewery_tag:
        return False
        
    result_brewery = brewery_tag.get_text(strip=True)
    
    # Simple normalization
    rb_norm = result_brewery.lower()
    eb_norm = expected_brewery.lower()
    
    # Check if one is contained in the other
    match = (rb_norm in eb_norm) or (eb_norm in rb_norm)
    if not match:
        logger.debug(f"Validation failed: Result brewery '{result_brewery}' != Expected '{expected_brewery}'")
    return match

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

    # Primary Search: beer_name + brewery_name
    parts = []
    if beer_name: parts.append(beer_name)
    if brewery_name: parts.append(brewery_name)
    
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
        logger.info(f"Retrying with Japanese name: {beer_name_jp}")
        # Validation might be hard with EN brewery name vs JP result, 
        # but often JP results have EN brewery name in Untappd too. 
        # We'll try strictly if we have brewery name, otherwise permissive.
        result = search_untappd(beer_name_jp, validate_brewery=brewery_name)
        if result:
            logger.info(f"Found direct link (JP name): {result}")
            return result
            
    # Final Fallback: Return search URL
    final_query = search_query if search_query.strip() else (beer_name or beer_name_jp or "")
    encoded_query = urllib.parse.quote(final_query)
    fallback_url = f"https://untappd.com/search?q={encoded_query}"
    logger.info("No direct link found. Returning search URL.")
    return fallback_url

def scrape_beer_details(url: str) -> UntappdBeerDetails:
    """
    Scrapes detailed info from a specific Untappd beer URL.
    
    Args:
        url (str): The valid Untappd beer page URL.
        
    Returns:
        UntappdBeerDetails: Dictionary containing beer details.
                            Returns empty dict on failure.
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
        if brewery_tag: details['untappd_brewery_name'] = brewery_tag.get_text(strip=True)
        
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Integration test
    test_url = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    # print(get_untappd_url("Inkhorn Brewing", "UGUISU"))
    print(scrape_beer_details(test_url))

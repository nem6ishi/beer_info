import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from typing import Optional, Dict
import time

def get_untappd_url(brewery_name: str, beer_name: str) -> Optional[str]:
    """
    Searches for an Untappd beer page using direct scraping of Untappd.com.
    
    Args:
        brewery_name (str): Name of the brewery (prefer English).
        beer_name (str): Name of the beer (prefer English).
        
    Returns:
        Optional[str]: A direct beer page URL (e.g. https://untappd.com/b/...) if found,
                       otherwise the Untappd search result page URL, or None if inputs are empty.
    """
    if not brewery_name and not beer_name:
        return None

    def search_untappd(query: str) -> Optional[str]:
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
                
                if results:
                    first_res = results[0]
                    name_tag = first_res.select_one('.name a')
                    
                    if name_tag:
                        href = name_tag.get('href')
                        if href and "/b/" in href:
                            full_url = f"https://untappd.com{href}"
                            return full_url
        except Exception as e:
            print(f"[Untappd] Search error: {e}")
        
        return None

    # Primary Search: beer_name + brewery_name (prefer English)
    parts = []
    if beer_name: parts.append(beer_name)
    if brewery_name: parts.append(brewery_name)
    
    search_query = " ".join(parts)
    print(f"[Untappd] Searching: {search_query}")
    
    result = search_untappd(search_query)
    if result:
        print(f"[Untappd] Found direct link: {result}")
        return result
    
    # Fallback Search: beer_name only
    if beer_name and brewery_name:
        print(f"[Untappd] Fallback search: {beer_name}")
        result = search_untappd(beer_name)
        if result:
            print(f"[Untappd] Found direct link (fallback): {result}")
            return result
    
    # Final Fallback: Return search URL
    encoded_query = urllib.parse.quote(search_query)
    fallback_url = f"https://untappd.com/search?q={encoded_query}"
    print("[Untappd] No direct link found. Returning search URL.")
    return fallback_url

def scrape_beer_details(url: str) -> Dict[str, str]:
    """
    Scrapes detailed info from a specific Untappd beer URL.
    
    Args:
        url (str): The valid Untappd beer page URL.
        
    Returns:
        Dict[str, str]: Dictionary containing:
            - untappd_beer_name
            - untappd_brewery_name
            - untappd_style
            - untappd_abv
            - untappd_ibu
            - untappd_rating
            - untappd_rating_count
            - untappd_fetched_at (ISO format datetime string)
            Returns empty dict on failure.
    """
    details = {}
    if not url or "untappd.com/b/" not in url:
        return details

    print(f"[Untappd] Scraping details from: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[Untappd] Failed to load details. Status: {resp.status_code}")
            return details
            
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Name & Brewery
        name_tag = soup.select_one('.name h1')
        if name_tag: details['untappd_beer_name'] = name_tag.get_text(strip=True)
        
        brewery_tag = soup.select_one('.name .brewery')
        if brewery_tag: details['untappd_brewery_name'] = brewery_tag.get_text(strip=True)
        
        style_tag = soup.select_one('.name .style')
        if style_tag: details['untappd_style'] = style_tag.get_text(strip=True)
        
        # Details Block (ABV, IBU, Rating, Count)
        abv_tag = soup.select_one('.details .abv')
        if abv_tag: 
            details['untappd_abv'] = abv_tag.get_text(strip=True).replace(' ABV', '')
            
        ibu_tag = soup.select_one('.details .ibu')
        if ibu_tag:
            details['untappd_ibu'] = ibu_tag.get_text(strip=True).replace(' IBU', '')
            
        rating_tag = soup.select_one('.details .num')
        if rating_tag:
            # Format is usually "(3.75)"
            details['untappd_rating'] = rating_tag.get_text(strip=True).strip('()')
            
        raters_tag = soup.select_one('.details .raters')
        if raters_tag:
            # Remove both "Rating" and "Ratings", and clean up parentheses
            count_text = raters_tag.get_text(strip=True)
            count_text = count_text.replace(' Ratings', '').replace(' Rating', '')
            count_text = count_text.strip('()')
            details['untappd_rating_count'] = count_text

        # Add timestamp
        details['untappd_fetched_at'] = datetime.now().isoformat()

    except Exception as e:
        print(f"[Untappd] Detail scrape error: {e}")
        
    return details

if __name__ == "__main__":
    # Integration test
    test_url = "https://untappd.com/b/inkhorn-brewing-uguisu/6441649"
    # print(get_untappd_url("Inkhorn Brewing", "UGUISU"))
    print(scrape_beer_details(test_url))

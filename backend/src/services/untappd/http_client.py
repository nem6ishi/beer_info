"""
HTTP client functions for Untappd scraping.
Split from searcher.py for better modularity.
"""
import logging
import urllib.parse
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
import requests
from bs4 import BeautifulSoup, Tag
from .text_utils import normalize_for_comparison
from ...core.types import UntappdBeerDetails, UntappdBreweryDetails

logger = logging.getLogger(__name__)

_UA: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_HEADERS: Dict[str, str] = {"User-Agent": _UA}


def search_brewery_beer(brewery_url: str, query: str, validate_beer_fn: Optional[Callable[[Tag, str], bool]] = None, validate_beer: Optional[str] = None) -> Optional[str]:
    """
    Searches for a beer within a specific brewery's page on Untappd.
    Navigate to /beer?q={query}&sort=created_at_desc

    Args:
        brewery_url: Untappd brewery page URL.
        query: Search query string for the beer.
        validate_beer_fn: Callable[[element, str], bool] for beer name validation.
        validate_beer: Expected beer name string (used with validate_beer_fn).
    """
    if not brewery_url or not query:
        return None

    encoded_query: str = urllib.parse.quote(query)
    base_url: str = brewery_url.rstrip('/')
    url: str = f"{base_url}/beer?q={encoded_query}&sort=created_at_desc"

    try:
        resp: requests.Response = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')
            results: List[Tag] = soup.select('.beer-item')
            for res in results[:5]:
                name_tag: Optional[Tag] = res.select_one('.name a')
                if name_tag:
                    href: Optional[str] = name_tag.get('href')
                    if href and "/b/" in href:
                        if validate_beer and validate_beer_fn and not validate_beer_fn(res, validate_beer):
                            continue
                        return f"https://untappd.com{href}"
    except Exception as e:
        logger.error(f"Brewery beer search error for '{query}' at {brewery_url}: {e}")

    return None


def scrape_beer_details(url: str) -> UntappdBeerDetails:
    """Scrapes detailed info from a specific Untappd beer URL."""
    details: UntappdBeerDetails = {}
    if not url or "untappd.com/b/" not in url:
        return details

    logger.info(f"Scraping details from: {url}")

    try:
        resp: requests.Response = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Failed to load details. Status: {resp.status_code}")
            return details

        soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')

        # Name & Brewery
        name_tag: Optional[Tag] = soup.select_one('.name h1')
        if name_tag:
            details['untappd_beer_name'] = name_tag.get_text(strip=True)

        brewery_tag: Optional[Tag] = soup.select_one('.name .brewery')
        if brewery_tag:
            brewery_link: Optional[Tag] = brewery_tag.select_one('a')
            if brewery_link:
                details['untappd_brewery_name'] = brewery_link.get_text(strip=True)
            else:
                details['untappd_brewery_name'] = brewery_tag.get_text(strip=True)
            if brewery_link and brewery_link.get('href'):
                href: str = brewery_link.get('href', '')
                details['untappd_brewery_url'] = f"https://untappd.com{href}" if href.startswith('/') else href

        style_tag: Optional[Tag] = soup.select_one('.name .style')
        if style_tag:
            details['untappd_style'] = style_tag.get_text(strip=True)

        # Label Image: Prioritize og:image for higher resolution
        og_image: Optional[Tag] = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            details['untappd_label'] = og_image['content']
        else:
            label_tag: Optional[Tag] = soup.select_one('.label img')
            if label_tag and label_tag.has_attr('src'):
                details['untappd_label'] = label_tag['src']

        abv_tag: Optional[Tag] = soup.select_one('.details .abv')
        if abv_tag:
            details['untappd_abv'] = abv_tag.get_text(strip=True).replace(' ABV', '')

        ibu_tag: Optional[Tag] = soup.select_one('.details .ibu')
        if ibu_tag:
            details['untappd_ibu'] = ibu_tag.get_text(strip=True).replace(' IBU', '')

        rating_tag: Optional[Tag] = soup.select_one('.details .num')
        if rating_tag:
            details['untappd_rating'] = rating_tag.get_text(strip=True).strip('()')

        raters_tag: Optional[Tag] = soup.select_one('.details .raters')
        if raters_tag:
            count_text: str = raters_tag.get_text(strip=True)
            count_text = count_text.replace(' Ratings', '').replace(' Rating', '').strip('()')
            details['untappd_rating_count'] = count_text

        details['untappd_fetched_at'] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"Detail scrape error: {e}")

    return details


def scrape_brewery_details(url: str) -> UntappdBreweryDetails:
    """Scrapes detailed info from a specific Untappd brewery URL."""
    details: UntappdBreweryDetails = {}
    if not url:
        return details

    logger.info(f"Scraping brewery details from: {url}")
    headers: Dict[str, str] = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://untappd.com/"
    }

    try:
        resp: requests.Response = requests.get(url, headers=headers, timeout=10)
        html: str = resp.text
        if resp.status_code != 200:
            logger.warning(f"requests failed ({resp.status_code}). Trying curl fallback...")
            curl_cmd: List[str] = [
                'curl', '-s', '-L',
                '-H', f"User-Agent: {headers['User-Agent']}",
                '-H', f"Accept: {headers['Accept']}",
                '-H', f"Referer: {headers['Referer']}",
                url
            ]
            curl_res: subprocess.CompletedProcess = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=15)
            if curl_res.returncode == 0 and len(curl_res.stdout) > 1000:
                html = curl_res.stdout
                logger.info("  ✅ Curl fallback successful")
            else:
                logger.error(f"  ❌ Curl fallback failed (code: {curl_res.returncode})")
                return details

        soup: BeautifulSoup = BeautifulSoup(html, 'lxml')

        name_tag: Optional[Tag] = soup.select_one('h1')
        if name_tag:
            details['brewery_name'] = name_tag.get_text(strip=True)
            parent: Optional[Tag] = name_tag.parent
            if parent:
                for p in parent.select('p'):
                    text: str = p.get_text(strip=True)
                    if "Subsidiary of" in text:
                        continue
                    if not details.get('location') and any(c.isalpha() for c in text):
                        details['location'] = text
                    elif not details.get('brewery_type') and details.get('location') and text != details.get('location'):
                        details['brewery_type'] = text

        # Logo
        og_image: Optional[Tag] = soup.find('meta', property='og:image')
        if og_image and og_image.get('content') and 'brewery_logos' in og_image.get('content'):
            details['logo_url'] = og_image.get('content')

        if not details.get('logo_url'):
            logo_img: Optional[Tag] = soup.select_one('.label img') or soup.select_one('.basic img') or soup.select_one('.logo img')
            if logo_img:
                details['logo_url'] = logo_img.get('src')

        # Website
        for link in soup.select('.social a'):
            text_link: str = link.get_text(strip=True).lower()
            href_link: Optional[str] = link.get('href')
            if 'website' in text_link or 'globe' in str(link):
                details['website'] = href_link

        # Stats
        stats_container: Optional[Tag] = soup.select_one('.stats')
        if stats_container:
            stats: Dict[str, str] = {}
            for item in stats_container.select('.item'):
                label_tag: Optional[Tag] = item.select_one('.title')
                value_tag: Optional[Tag] = item.select_one('.count')
                if label_tag and value_tag:
                    l_text: str = label_tag.get_text(strip=True).lower()
                    v_text: str = value_tag.get_text(strip=True).replace(',', '')
                    if 'total' in l_text:
                        stats['total_beers'] = v_text
                    elif 'unique' in l_text:
                        stats['unique_users'] = v_text
                    elif 'monthly' in l_text:
                        stats['monthly_checkins'] = v_text
                    elif 'ratings' in l_text:
                        stats['rating_count'] = v_text
            details['stats'] = stats

        details['fetched_at'] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"Brewery scrape error: {e}")

    return details


def search_brewery(query: str) -> Optional[str]:
    """Searches for a brewery on Untappd and returns the brewery page URL."""
    encoded_query: str = urllib.parse.quote(query)
    url: str = f"https://untappd.com/search?q={encoded_query}&type=brewery"

    try:
        resp: requests.Response = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')
            for res in soup.select('.beer-item')[:1]:
                name_tag: Optional[Tag] = res.select_one('.name a')
                if name_tag:
                    href: Optional[str] = name_tag.get('href')
                    if href and "/b/" not in href:
                        return f"https://untappd.com{href}"
    except Exception as e:
        logger.error(f"Brewery search error for '{query}': {e}")

    return None

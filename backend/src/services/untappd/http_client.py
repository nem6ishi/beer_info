"""
HTTP client functions for Untappd scraping.
Split from searcher.py for better modularity.
"""
import asyncio
import logging
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Callable, List
import httpx
from bs4 import BeautifulSoup, Tag
from ...core.types import UntappdBeerDetails, UntappdBreweryDetails
from .text_utils import normalize_for_comparison

logger = logging.getLogger(__name__)

_UA: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_HEADERS: Dict[str, str] = {"User-Agent": _UA}

_async_client: Optional[httpx.AsyncClient] = None


def get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        _async_client = httpx.AsyncClient(
            headers=_HEADERS,
            timeout=httpx.Timeout(15.0, connect=10.0),
            follow_redirects=True,
            limits=limits,
        )
    return _async_client


async def close_async_client() -> None:
    global _async_client
    if _async_client is not None and not _async_client.is_closed:
        await _async_client.aclose()
        _async_client = None


async def search_brewery_beer(
    brewery_url: str,
    query: str,
    validate_beer_fn: Optional[Callable[[Tag, str], bool]] = None,
    validate_beer: Optional[str] = None,
    score_beer_fn: Optional[Callable[[Tag, str], int]] = None,
) -> Optional[str]:
    if not brewery_url or not query:
        return None

    encoded_query: str = urllib.parse.quote(query)
    base_url: str = brewery_url.rstrip('/')
    url: str = f"{base_url}/beer?q={encoded_query}&sort=created_at_desc"

    try:
        client = get_async_client()
        resp: httpx.Response = await client.get(url)
        if resp.status_code == 200:
            soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')
            results: List[Tag] = soup.select('.beer-item')

            if score_beer_fn and validate_beer:
                candidates: List[tuple] = []
                for res in results[:10]:
                    name_tag: Optional[Tag] = res.select_one('.name a')
                    if name_tag:
                        href: Optional[str] = name_tag.get('href')
                        if href and "/b/" in href:
                            score = score_beer_fn(res, validate_beer)
                            if score > 0:
                                full_url = f"https://untappd.com{href}"
                                beer_text = name_tag.get_text(strip=True)
                                candidates.append((score, full_url, beer_text))

                if candidates:
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_url, best_name = candidates[0]
                    logger.info(
                        f"  [Scoring] Best match: '{best_name}' (score={best_score}) "
                        f"from {len(candidates)} candidates"
                    )
                    if len(candidates) > 1:
                        for s, u, n in candidates[1:]:
                            logger.debug(f"  [Scoring]   Also matched: '{n}' (score={s})")
                    return best_url
                return None

            for res in results[:5]:
                name_tag_legacy: Optional[Tag] = res.select_one('.name a')
                if name_tag_legacy:
                    href_legacy: Optional[str] = name_tag_legacy.get('href')
                    if href_legacy and "/b/" in href_legacy:
                        if validate_beer and validate_beer_fn and not validate_beer_fn(res, validate_beer):
                            continue
                        return f"https://untappd.com{href_legacy}"
    except Exception as e:
        logger.error(f"Brewery beer search error for '{query}' at {brewery_url}: {e}")

    return None


async def scrape_beer_details(url: str) -> UntappdBeerDetails:
    details: UntappdBeerDetails = {}
    if not url or "untappd.com/b/" not in url:
        return details

    logger.info(f"Scraping details from: {url}")

    try:
        client = get_async_client()
        resp: httpx.Response = await client.get(url)
        if resp.status_code != 200:
            logger.warning(f"Failed to load details. Status: {resp.status_code}")
            return details

        soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')

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

        label_tag: Optional[Tag] = soup.select_one('.label img')
        if label_tag and label_tag.has_attr('src'):
            details['untappd_label'] = label_tag['src']
        else:
            og_image: Optional[Tag] = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                details['untappd_label'] = og_image['content']

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


async def scrape_brewery_details(url: str) -> UntappdBreweryDetails:
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
        client = get_async_client()
        resp: httpx.Response = await client.get(url, headers=headers)
        html: str = resp.text
        if resp.status_code != 200:
            logger.warning(f"httpx failed ({resp.status_code}). Trying curl fallback...")
            curl_cmd: List[str] = [
                'curl', '-s', '-L',
                '-H', f"User-Agent: {headers['User-Agent']}",
                '-H', f"Accept: {headers['Accept']}",
                '-H', f"Referer: {headers['Referer']}",
                url
            ]
            proc = await asyncio.create_subprocess_exec(
                *curl_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            if proc.returncode == 0 and len(stdout) > 1000:
                html = stdout.decode('utf-8', errors='ignore')
                logger.info("  ✅ Curl fallback successful")
            else:
                logger.error(f"  ❌ Curl fallback failed (code: {proc.returncode})")
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

        og_image: Optional[Tag] = soup.find('meta', property='og:image')
        if og_image and og_image.get('content') and 'brewery_logos' in og_image.get('content'):
            details['logo_url'] = og_image.get('content')

        if not details.get('logo_url'):
            logo_img: Optional[Tag] = soup.select_one('.label img') or soup.select_one('.basic img') or soup.select_one('.logo img')
            if logo_img:
                details['logo_url'] = logo_img.get('src')

        for link in soup.select('.social a'):
            text_link: str = link.get_text(strip=True).lower()
            href_link: Optional[str] = link.get('href')
            if 'website' in text_link or 'globe' in str(link):
                details['website'] = href_link

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


async def search_brewery(query: str) -> Optional[str]:
    encoded_query: str = urllib.parse.quote(query)
    url: str = f"https://untappd.com/search?q={encoded_query}&type=brewery"

    try:
        client = get_async_client()
        resp: httpx.Response = await client.get(url)
        if resp.status_code == 200:
            soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')
            
            candidates = []
            for res in soup.select('.beer-item')[:5]:
                name_tag: Optional[Tag] = res.select_one('.name a')
                if name_tag:
                    href: Optional[str] = name_tag.get('href')
                    if href and "/b/" not in href:
                        name_text = name_tag.get_text(strip=True)
                        candidates.append((name_text, f"https://untappd.com{href}"))
            
            if not candidates:
                return None
                
            query_norm = normalize_for_comparison(query)
            
            for name, link in candidates:
                if normalize_for_comparison(name) == query_norm:
                    logger.info(f"  [Brewery Search] Exact match found: {name}")
                    return link
                    
            for name, link in candidates:
                if query_norm in normalize_for_comparison(name):
                    logger.info(f"  [Brewery Search] Partial match found: {name}")
                    return link
                    
            logger.info(f"  [Brewery Search] No exact match, falling back to first: {candidates[0][0]}")
            return candidates[0][1]

    except Exception as e:
        logger.error(f"Brewery search error for '{query}': {e}")

    return None

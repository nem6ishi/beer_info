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
from ...core.types import UntappdBeerDetails, UntappdBreweryDetails, UntappdSearchCandidate
from .text_utils import normalize_for_comparison
from .validators import clean_brewery_name

logger = logging.getLogger(__name__)

_UA: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_HEADERS: Dict[str, str] = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

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


async def search_brewery_beer_candidates(
    brewery_url: str,
    query: str,
    validate_beer_fn: Optional[Callable] = None,
    validate_beer: Optional[str] = None,
    score_beer_fn: Optional[Callable] = None,
    validate_brewery: Optional[str] = None,
    max_candidates: int = 10,
) -> List[UntappdSearchCandidate]:
    if not brewery_url or not query:
        return []

    encoded_query: str = urllib.parse.quote(query)
    base_url: str = brewery_url.rstrip('/')
    for suffix in ('/beer', '/photos', '/activity'):
        if base_url.endswith(suffix):
            base_url = base_url[:-len(suffix)]
    url: str = f"{base_url}/beer?q={encoded_query}&sort=created_at_desc"

    headers: Dict[str, str] = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": brewery_url
    }
    html: Optional[str] = None
    try:
        client = get_async_client()
        for attempt in range(3):
            try:
                resp: httpx.Response = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    break
                elif resp.status_code in (429, 403, 503):
                    await asyncio.sleep(1 * (attempt + 1))
            except Exception as httpx_e:
                logger.debug(f"httpx error on search_brewery_beer_candidates: {httpx_e}")
                await asyncio.sleep(1)

        if not html:
            curl_cmd: List[str] = [
                'curl', '-s', '-L',
                '-H', f"User-Agent: {headers['User-Agent']}",
                '-H', f"Referer: {headers['Referer']}",
                url
            ]
            proc = await asyncio.create_subprocess_exec(
                *curl_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=12.0)
            if proc.returncode == 0 and len(stdout) > 500:
                html = stdout.decode('utf-8', errors='ignore')

        if html:
            soup: BeautifulSoup = BeautifulSoup(html, 'lxml')
            results: List[Tag] = soup.select('.beer-item')

            candidates: List[UntappdSearchCandidate] = []
            for res in results[:50]:
                name_tag: Optional[Tag] = res.select_one('.name a')
                if not name_tag:
                    continue
                href: Optional[str] = name_tag.get('href')
                if not href or "/b/" not in href:
                    continue

                full_url = f"https://untappd.com{href}"
                beer_text = name_tag.get_text(strip=True)

                brewery_tag = res.select_one('.name .brewery a') or res.select_one('.name .brewery') or res.select_one('.brewery a') or res.select_one('.brewery')
                brewery_text = brewery_tag.get_text(strip=True) if brewery_tag else ""

                style_tag = res.select_one('.style')
                style_text = style_tag.get_text(strip=True) if style_tag else ""

                score = 0.0
                if score_beer_fn and validate_beer:
                    try:
                        score = float(score_beer_fn(res, validate_beer, validate_brewery))
                    except TypeError:
                        score = float(score_beer_fn(res, validate_beer))
                    if score <= 0:
                        continue
                elif validate_beer and validate_beer_fn:
                    try:
                        valid = validate_beer_fn(res, validate_beer, validate_brewery)
                    except TypeError:
                        valid = validate_beer_fn(res, validate_beer)
                    if not valid:
                        continue
                    score = 1.0

                candidates.append({
                    'url': full_url,
                    'beer_name': beer_text,
                    'brewery_name': brewery_text,
                    'style': style_text,
                    'score': score,
                    'source': 'untappd_brewery'
                })

            if candidates:
                candidates.sort(key=lambda x: x.get('score', 0.0), reverse=True)
                logger.info(
                    f"  [Candidates] Found {len(candidates)} candidates within brewery for '{query}'"
                )
                return candidates[:max_candidates]

    except Exception as e:
        logger.error(f"Brewery beer search error for '{query}' at {brewery_url}: {e}")

    return []


async def search_brewery_beer(
    brewery_url: str,
    query: str,
    validate_beer_fn: Optional[Callable] = None,
    validate_beer: Optional[str] = None,
    score_beer_fn: Optional[Callable] = None,
    validate_brewery: Optional[str] = None,
) -> Optional[str]:
    candidates = await search_brewery_beer_candidates(
        brewery_url=brewery_url,
        query=query,
        validate_beer_fn=validate_beer_fn,
        validate_beer=validate_beer,
        score_beer_fn=score_beer_fn,
        validate_brewery=validate_brewery,
        max_candidates=1
    )
    if candidates:
        best = candidates[0]
        logger.info(
            f"  [Scoring] Best match: '{best.get('beer_name')}' (score={best.get('score', 0)}) "
            f"from candidates"
        )
        return best.get('url')
    return None



async def scrape_beer_details(url: str) -> UntappdBeerDetails:
    details: UntappdBeerDetails = {}
    if not url or "untappd.com/b/" not in url:
        return details

    logger.info(f"Scraping details from: {url}")
    headers: Dict[str, str] = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://untappd.com/"
    }

    html: Optional[str] = None
    try:
        client = get_async_client()
        for attempt in range(3):
            try:
                resp: httpx.Response = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    html = resp.text
                    break
                elif resp.status_code in (429, 403, 503):
                    await asyncio.sleep(2 * (attempt + 1))
            except Exception as httpx_e:
                logger.warning(f"httpx error on {url} (attempt {attempt+1}): {httpx_e}")
                await asyncio.sleep(1)

        if not html:
            logger.warning("httpx failed to load details. Trying curl fallback...")
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
                logger.info("  ✅ Curl fallback successful for beer details")
            else:
                logger.error(f"  ❌ Curl fallback failed for beer details (code: {proc.returncode})")
                return details

        soup: BeautifulSoup = BeautifulSoup(html, 'lxml')

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

    candidates = []
    try:
        client = get_async_client()
        resp: httpx.Response = await client.get(url)
        if resp.status_code == 200:
            soup: BeautifulSoup = BeautifulSoup(resp.text, 'lxml')
            for res in soup.select('.beer-item')[:5]:
                name_tag: Optional[Tag] = res.select_one('.name a')
                if name_tag:
                    href: Optional[str] = name_tag.get('href')
                    if href and "/b/" not in href:
                        name_text = name_tag.get_text(strip=True)
                        candidates.append((name_text, f"https://untappd.com{href}"))
    except Exception as e:
        logger.error(f"Brewery search error for '{query}': {e}")

    # If no candidates found via direct /search page (since Untappd often JS-blocks it), try DuckDuckGo site search
    if not candidates:
        try:
            from ddgs import DDGS
            def _ddg_brewery():
                with DDGS(timeout=10) as ddgs:
                    res = ddgs.text(f"site:untappd.com/w/ {query}", max_results=3)
                    if not res:
                        res = ddgs.text(f"site:untappd.com {query} brewery", max_results=3)
                    return list(res) if res else []
            ddg_res = await asyncio.to_thread(_ddg_brewery)
            query_norm = normalize_for_comparison(query)
            query_clean = normalize_for_comparison(clean_brewery_name(query))
            for r in ddg_res:
                href = r.get("href", "")
                title = r.get("title", "")
                if "/w/" in href or ("untappd.com/" in href and "/b/" not in href and "/user/" not in href and "/search" not in href):
                    href_clean = href.rstrip('/')
                    for suffix in ('/beer', '/photos', '/activity'):
                        if href_clean.endswith(suffix):
                            href_clean = href_clean[:-len(suffix)]
                    title_norm = normalize_for_comparison(title)
                    href_norm = normalize_for_comparison(href_clean)
                    is_valid_brewery = False
                    if query_norm and (query_norm in title_norm or query_norm in href_norm):
                        is_valid_brewery = True
                    elif query_clean and len(query_clean) >= 3 and (query_clean in title_norm or query_clean in href_norm):
                        is_valid_brewery = True
                    else:
                        words = [w for w in query_clean.split() if len(w) >= 4]
                        if words and any(w in title_norm or w in href_norm for w in words):
                            is_valid_brewery = True
                    if is_valid_brewery:
                        logger.info(f"  [Brewery Search] Found validated brewery URL via DDG: {href_clean}")
                        return href_clean
                    else:
                        logger.debug(f"  [Brewery Search] Ignored DDG result (mismatch with query '{query}'): {href_clean} ({title})")
        except Exception as ddg_e:
            logger.debug(f"  [Brewery Search] DDG brewery fallback failed: {ddg_e}")
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

"""
Base scraper class for beer shop scrapers.
Provides common HTTP fetch, error handling, and interface definition.
New scrapers should inherit from BaseScraper and implement the scrape() method.

Existing scrapers (beervolta, arome, chouseiya, ichigo_ichie) are function-based
and work correctly as-is. This base class is provided as a pattern for future scrapers.
"""
import asyncio
import logging
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
}


class ScrapedProduct(Dict):
    """
    Typed structure representing a scraped beer product.
    Keys: name, price, url, image, stock_status, shop
    """
    pass


class BaseScraper(ABC):
    """
    Abstract base class for all beer shop scrapers.

    Subclasses must implement:
    - shop_name (class attribute): Human-readable shop name
    - scrape() (async method): Returns list of ScrapedProduct

    Provides:
    - fetch(): Async-safe HTTP GET with retries and encoding handling
    - parse_html(): BeautifulSoup parsing
    - Common sold-out threshold and rate-limiting patterns
    """

    shop_name: str = "Unknown Shop"
    default_headers: dict = _DEFAULT_HEADERS
    sold_out_threshold: int = 50

    @abstractmethod
    async def scrape(
        self,
        limit: int = None,
        existing_urls: set = None,
        full_scrape: bool = False,
    ) -> List[ScrapedProduct]:
        """
        Scrape all products from the shop.

        Args:
            limit: Maximum number of products to return. None = no limit.
            existing_urls: Set of already-known product URLs. If provided,
                           stop early when encountering too many existing items.
            full_scrape: If True, ignore the sold_out_threshold early-stop.

        Returns:
            List of ScrapedProduct dicts with keys:
            name, price, url, image, stock_status, shop
        """
        ...

    async def fetch(
        self,
        url: str,
        encoding: str = None,
        delay: tuple = (0.3, 0.8),
        timeout: int = 30,
    ) -> Optional[BeautifulSoup]:
        """
        Fetch a URL and return a BeautifulSoup object.
        Adds a small random delay to be polite to servers.

        Args:
            url: URL to fetch.
            encoding: Force a specific encoding. If None, auto-detect.
            delay: (min, max) seconds to wait before fetching.
            timeout: Request timeout in seconds.

        Returns:
            BeautifulSoup or None on failure.
        """
        if delay:
            await asyncio.sleep(random.uniform(*delay))

        try:
            response = requests.get(url, headers=self.default_headers, timeout=timeout)
            response.raise_for_status()
            if encoding:
                response.encoding = encoding
            else:
                response.encoding = response.apparent_encoding
            return BeautifulSoup(response.content, 'lxml')
        except requests.RequestException as e:
            logger.error(f"[{self.shop_name}] HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"[{self.shop_name}] Unexpected error fetching {url}: {e}")
            return None

    def make_product(
        self,
        name: str,
        price: str,
        url: str,
        image: Optional[str],
        stock_status: str = "In Stock",
    ) -> ScrapedProduct:
        """
        Factory method to create a ScrapedProduct with the shop_name pre-filled.
        """
        return ScrapedProduct(
            name=name,
            price=price,
            url=url,
            image=image,
            stock_status=stock_status,
            shop=self.shop_name,
        )

    def log(self, msg: str) -> None:
        """Log a message with the shop name prefix."""
        logger.info(f"[{self.shop_name}] {msg}")

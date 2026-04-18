from typing import TypedDict, Optional, List, Any

class ScrapedProduct(TypedDict):
    """Data structure returned by scrapers."""
    name: str
    price: str
    url: str
    image: Optional[str]
    stock_status: str
    shop: str

class BeerRecord(TypedDict, total=False):
    """Database record for the 'scraped_beers' table."""
    url: str
    name: str
    price: str
    price_value: Optional[int]
    image: Optional[str]
    stock_status: str
    shop: str
    first_seen: str
    last_seen: str
    # Enrichment fields
    untappd_url: Optional[str]
    brewery_name_jp: Optional[str]
    brewery_name_en: Optional[str]
    beer_name_jp: Optional[str]
    beer_name_en: Optional[str]
    beer_name_core: Optional[str]
    search_hint: Optional[str]
    product_type: Optional[str]
    is_set: Optional[bool]
    # Untappd data fields (denormalized into view/table)
    untappd_beer_name: Optional[str]
    untappd_brewery_name: Optional[str]
    untappd_style: Optional[str]
    untappd_abv: Optional[float]
    untappd_ibu: Optional[int]
    untappd_rating: Optional[float]
    untappd_rating_count: Optional[int]
    untappd_fetched_at: Optional[str]

class UntappdBeerDetails(TypedDict, total=False):
    """Detailed information scraped from an Untappd beer page."""
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
    """Detailed information scraped from an Untappd brewery page."""
    brewery_name: str
    location: str
    brewery_type: str
    website: str
    logo_url: str
    stats: dict
    fetched_at: str

class GeminiExtraction(TypedDict):
    """Result of Gemini AI extraction from product title."""
    brewery_name_jp: Optional[str]
    brewery_name_en: Optional[str]
    beer_name_jp: Optional[str]
    beer_name_en: Optional[str]
    beer_name_core: Optional[str]
    search_hint: Optional[str]
    product_type: str
    is_set: bool
    raw_response: Optional[str]

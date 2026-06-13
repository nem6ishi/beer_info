import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from backend.src.core.types import UntappdBeerDetails

def parse_numeric(val: Optional[str]) -> Optional[float]:
    """Helper to parse numeric values from strings."""
    if not val:
        return None
    try:
        # Remove non-numeric characters except dots
        clean = re.sub(r'[^0-9.]', '', str(val))
        return float(clean) if clean else None
    except Exception:
        return None

def map_details_to_payload(details: UntappdBeerDetails) -> Dict[str, Any]:
    """Maps scraper keys to untappd_data table columns."""
    return {
        'beer_name': details.get('untappd_beer_name'),
        'brewery_name': details.get('untappd_brewery_name'),
        'style': details.get('untappd_style'),
        'abv': details.get('untappd_abv'),
        'abv_num': parse_numeric(details.get('untappd_abv')),
        'ibu': details.get('untappd_ibu'),
        'ibu_num': parse_numeric(details.get('untappd_ibu')),
        'rating': details.get('untappd_rating'),
        'rating_num': parse_numeric(details.get('untappd_rating')),
        'rating_count': details.get('untappd_rating_count'),
        'rating_count_num': parse_numeric(details.get('untappd_rating_count')),
        'image_url': details.get('untappd_label'),
        'untappd_brewery_url': details.get('untappd_brewery_url'),
        'fetched_at': datetime.now(timezone.utc).isoformat()
    }

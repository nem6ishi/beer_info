"""
Text utility functions for beer/brewery name cleaning and normalization.
Split from searcher.py for better modularity.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Common beer style suffixes (sorted by length descending for greedy matching)
COMMON_SUFFIXES = [
    " IPA", " Hazy IPA", " Double IPA", " DIPA", " Triple IPA", " TIPA", " NEIPA",
    " NE IPA", " NE-IPA", " WCIPA", " WC IPA", " West Coast IPA", " Session IPA",
    " DDH IPA", " TDH IPA",
    " Pale Ale", " Stout", " Imperial Stout", " Lager", " Pilsner", " Sour",
    " Gose", " Porter", " Ale", " Wheat", " Saison", " Barleywine",
    " Lambic", " Gueuze", " Fruit Beer"
]

COMMON_SUFFIXES.sort(key=len, reverse=True)

# Ordinal number mapping for anniversary/edition names (e.g. 11th -> eleventh)
_ORDINAL_MAP = {
    '1st': 'first', '2nd': 'second', '3rd': 'third', '4th': 'fourth',
    '5th': 'fifth', '6th': 'sixth', '7th': 'seventh', '8th': 'eighth',
    '9th': 'ninth', '10th': 'tenth', '11th': 'eleventh', '12th': 'twelfth',
    '13th': 'thirteenth', '14th': 'fourteenth', '15th': 'fifteenth',
    '16th': 'sixteenth', '17th': 'seventeenth', '18th': 'eighteenth',
    '19th': 'nineteenth', '20th': 'twentieth', '21st': 'twentyfirst',
    '25th': 'twentyfifth', '30th': 'thirtieth',
}


def normalize_for_comparison(text: str) -> str:
    """Removes whitespace and non-alphanumeric characters for fuzzy comparison."""
    if not text:
        return ""
    return "".join(c.lower() for c in text if c.isalnum())


def normalize_ordinals(text: str) -> str:
    """Converts ordinal numbers (11th, 2nd, etc.) to their English word equivalents."""
    def replace_ordinal(m):
        return _ORDINAL_MAP.get(m.group(0).lower(), m.group(0))
    return re.sub(r'\b\d+(?:st|nd|rd|th)\b', replace_ordinal, text, flags=re.IGNORECASE)


def strip_for_core_comparison(text: str) -> str:
    """Strips year, style suffixes, dashes, and punctuation for core name comparison."""
    # Remove year in parens like (2026)
    text = re.sub(r'\s*\(20\d{2}\)\s*', ' ', text)
    # Remove em-dashes and en-dashes (common in Untappd names)
    text = re.sub(r'\s*[–—-]\s*', ' ', text)
    # Remove colons and everything after (often used for fruit additions in JP shops)
    text = re.sub(r':.*$', '', text)
    # Remove common beer style suffixes at end
    text = re.sub(
        r'\s+(?:IPA|DIPA|TIPA|Hazy IPA|Double IPA|Triple IPA|NEIPA|West Coast IPA|'
        r'Session IPA|Stout|Imperial Stout|Pale Ale|Lager|Pilsner|Sour|Porter|Ale|Saison|Gose)\s*$',
        '', text, flags=re.IGNORECASE
    )
    return text.strip()


def clean_beer_name(name: str) -> str:
    """
    Cleans beer name by removing common noise patterns:
    - Japanese series markers (〜, シリーズ, #XX, Vol.X)
    - Batch/version markers (Batch X, Ver.X, etc.)
    - Style descriptions in parentheses
    """
    if not name:
        return name

    original = name

    # Remove content after 〜 (wave dash - usually series info)
    name = re.sub(r'〜.*$', '', name)
    name = re.sub(r'~.*$', '', name)

    # Remove シリーズ and everything after
    name = re.sub(r'シリーズ.*$', '', name)

    # Remove hop treatment prefixes (TDH/DDH/SDH)
    name = re.sub(r'\b(?:TDH|DDH|SDH)\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\b(?:Triple|Double|Single)\s+Dry\s+Hopped\s+', '', name, flags=re.IGNORECASE)

    # Remove #XX, Vol.X, Batch X patterns
    name = re.sub(r'#\d+', '', name)
    name = re.sub(r'Vol\.?\s*\d+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'Batch\s*\d+', '', name, flags=re.IGNORECASE)

    # Remove Japanese parentheses content that looks like version info or anniversary
    name = re.sub(r'（[^）]*版[^）]*）', '', name)
    
    # Remove anything after a colon (often used for variants like "Name: Cherry/Vanilla")
    name = re.sub(r':.*$', '', name)

    # Remove style descriptions in parentheses
    name = re.sub(
        r'\s*\([^)]*(?:IPA|Lager|Stout|Ale|Saison|Porter|Pilsner|Pale|Hazy|DDH|TDH|DIPA|TIPA|Imperial|Session)[^)]*\)',
        '', name, flags=re.IGNORECASE
    )
    name = re.sub(r'\s*\([^)]*w/[^)]*\)', '', name)  # e.g., "(w/Cryo Fresh Hops)"

    # Remove standalone beer style descriptors
    name = re.sub(
        r'\s+(?:Imperial|Russian Imperial|American Imperial)\s+(?:Stout|IPA|Porter|Lager|Pale Ale)\b',
        '', name, flags=re.IGNORECASE
    )
    name = re.sub(
        r'\s+(?:West Coast|East Coast|New England|Hazy|Session|Double|Triple)\s+(?:IPA|Pale Ale|Lager)\b',
        '', name, flags=re.IGNORECASE
    )
    name = re.sub(
        r'\s+(?:Sour|Fruited|Barrel-Aged|Oak-Aged)\s+(?:Ale|Beer|Stout|IPA)\b',
        '', name, flags=re.IGNORECASE
    )
    # Single-word styles at the end
    name = re.sub(r'\s+(?:IPA|DIPA|TIPA|Stout|Porter|Lager|Pilsner|Saison|Ale)$', '', name, flags=re.IGNORECASE)

    # Remove -〇〇編- style suffixes
    name = re.sub(r'-[^-]+編-?$', '', name)
    name = re.sub(r'－[^－]+編－?$', '', name)

    # Remove version/multiplier markers (2x, 3x, etc.)
    name = re.sub(r'\s+\d+[xX]\s*', ' ', name)
    name = re.sub(r'\s+\d+[xX]$', '', name)

    # Normalize DR./MR./ST. etc.
    name = re.sub(r'\bDR\.\s*', 'Dr ', name, flags=re.IGNORECASE)
    name = re.sub(r'\bMR\.\s*', 'Mr ', name, flags=re.IGNORECASE)
    name = re.sub(r'\bST\.\s*', 'St ', name, flags=re.IGNORECASE)
    
    # Special: Remove parenthesis that contain long sentences (e.g. toe 25th Anniversary)
    # This prevents the search query from being too specific and failing entirely.
    name = re.sub(r'\([^)]+\)', '', name)

    # Clean up extra whitespace
    name = ' '.join(name.split())

    if name != original:
        logger.info(f"Cleaned beer name: '{original}' -> '{name}'")

    return name.strip()


def clean_brewery_name(name: str) -> str:
    """
    Cleans brewery name by removing common suffixes (Brewing, Brewery, Beer, etc.)
    for better search matching.
    """
    if not name:
        return name

    suffixes = [
        # English
        ' Beer Company', ' Brewing Co.', ' Brewing Company', ' Brewery Co.',
        ' Beer Co', ' Brewing', ' Brewery', ' Beer', ' Co.', ' Company', ' Corporation', ' Corp.',
        ' Brewhouse', ' Brewpub', ' Craft Beer',
        # Czech
        ' pivovar', ' pivovar a.s.', ' pivovarský dům',
        # Spanish
        ' cervecería', ' cerveza', ' cervezas',
        # German
        ' brauerei', ' bräu', ' brauhaus',
        # French
        ' brasserie',
        # Italian
        ' birrificio',
        # Japanese
        ' 醸造所', ' ブルワリー', ' ビール',
    ]
    suffixes.sort(key=len, reverse=True)

    original = name
    for suffix in suffixes:
        if name.lower().endswith(suffix.lower()):
            name = name[:-len(suffix)].strip()
            break

    if name != original:
        logger.info(f"Cleaned brewery name: '{original}' -> '{name}'")

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

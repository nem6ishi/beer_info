"""
Text utility functions for beer/brewery name cleaning and normalization.
Split from searcher.py for better modularity.
"""
import re
import logging
from typing import Optional, List, Dict, Match

logger = logging.getLogger(__name__)

# Regex pattern to safely split collaboration brewery names without breaking names like "Oxford"
COLLAB_SPLIT_PATTERN = r'\s+(?:x|X|with)\s+|\s*[×&/+]\s*|\s*w/\s*'

# Common abbreviations expanded for matching (applied before normalization).
# Keys are lowercase abbreviation patterns; values are the expanded form.
_ABBREVIATION_MAP: Dict[str, str] = {
    'ddh': 'double dry hopped',
    'tdh': 'triple dry hopped',
    'sdh': 'single dry hopped',
    'ba ': 'barrel aged ',
    'bba ': 'bourbon barrel aged ',
    'lr ': 'limited release ',
    'lr': 'limited release',
}


def expand_abbreviations(text: str) -> str:
    """Expands common beer abbreviations (DDH, TDH, LR, etc.) for better matching."""
    if not text:
        return text
    result = text
    # Expand numeric combinations like LR39 -> Limited Release 39
    result = re.sub(r'\bLR\s*([0-9]+)\b', r'Limited Release \1', result, flags=re.IGNORECASE)
    for abbr, expanded in _ABBREVIATION_MAP.items():
        # Case-insensitive replacement of whole-word abbreviations
        result = re.sub(r'\b' + re.escape(abbr.strip()) + r'\b', expanded.strip(), result, flags=re.IGNORECASE)
    return result


def normalize_for_comparison(text: str, expand_abbr: bool = False) -> str:
    """Removes whitespace and non-alphanumeric characters for fuzzy comparison.
    
    Args:
        text: Input string to normalize.
        expand_abbr: If True, expand abbreviations (DDH→Double Dry Hopped) before normalizing.
    """
    if not text:
        return ""
    if expand_abbr:
        text = expand_abbreviations(text)
    return "".join(c.lower() for c in text if c.isalnum())


# Common beer style suffixes (sorted by length descending for greedy matching)
COMMON_SUFFIXES: List[str] = [
    " Sake IPA", " Sake Ale", " Rice Ale", " Sake",
    " IPA", " Hazy IPA", " Double IPA", " DIPA", " Triple IPA", " TIPA", " NEIPA",
    " NE IPA", " NE-IPA", " WCIPA", " WC IPA", " West Coast IPA", " Session IPA",
    " DDH IPA", " TDH IPA",
    " Pale Ale", " Stout", " Imperial Stout", " Lager", " Pilsner", " Sour",
    " Gose", " Porter", " Ale", " Wheat", " Saison", " Barleywine",
    " Lambic", " Gueuze", " Fruit Beer"
]

COMMON_SUFFIXES.sort(key=len, reverse=True)

# Ordinal number mapping for anniversary/edition names (e.g. 11th -> eleventh)
_ORDINAL_MAP: Dict[str, str] = {
    '1st': 'first', '2nd': 'second', '3rd': 'third', '4th': 'fourth',
    '5th': 'fifth', '6th': 'sixth', '7th': 'seventh', '8th': 'eighth',
    '9th': 'ninth', '10th': 'tenth', '11th': 'eleventh', '12th': 'twelfth',
    '13th': 'thirteenth', '14th': 'fourteenth', '15th': 'fifteenth',
    '16th': 'sixteenth', '17th': 'seventeenth', '18th': 'eighteenth',
    '19th': 'nineteenth', '20th': 'twentieth', '21st': 'twentyfirst',
    '25th': 'twentyfifth', '30th': 'thirtieth',
}

# Number and Roman numeral mappings to Arabic digits
_ROMAN_UNICODE_MAP: Dict[str, str] = {
    'Ⅰ': '1', 'Ⅱ': '2', 'Ⅲ': '3', 'Ⅳ': '4', 'Ⅴ': '5',
    'Ⅵ': '6', 'Ⅶ': '7', 'Ⅷ': '8', 'Ⅸ': '9', 'Ⅹ': '10',
    'ⅰ': '1', 'ⅱ': '2', 'ⅲ': '3', 'ⅳ': '4', 'ⅴ': '5',
    'ⅵ': '6', 'ⅶ': '7', 'ⅷ': '8', 'ⅸ': '9', 'ⅹ': '10',
}

_WORD_NUMBER_MAP: Dict[str, str] = {
    'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'ii': '2', 'iii': '3', 'iv': '4', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9',
}


def normalize_numbers_and_romans(text: str) -> str:
    """Converts Roman numerals (Ⅲ, III) and word numbers (Three) to Arabic digits (3)."""
    if not text:
        return ""
    result = text
    for char, digit in _ROMAN_UNICODE_MAP.items():
        result = result.replace(char, digit)
    def replace_word(m: re.Match) -> str:
        word = m.group(0).lower()
        return _WORD_NUMBER_MAP.get(word, m.group(0))
    result = re.sub(r'\b[a-zA-Z]+\b', replace_word, result)
    return result


def normalize_singular_plural(text: str) -> str:
    """Normalizes plural and singular English words (e.g. Fruits -> Fruit, Berries -> Berry) for robust matching."""
    if not text:
        return ""
    def _stem_word(w: str) -> str:
        w_lower = w.lower()
        if len(w_lower) > 4 and w_lower.endswith('ies'):
            return w[:-3] + ('y' if w.islower() else 'Y')
        if len(w_lower) > 4 and w_lower.endswith('es') and w_lower[-3] in 'xzsh':
            return w[:-2]
        if len(w_lower) > 3 and w_lower.endswith('s') and not w_lower.endswith(('ss', 'us', 'is', 'as', 'os', 'ys')):
            return w[:-1]
        return w
    return re.sub(r'\b[a-zA-Z]+\b', lambda m: _stem_word(m.group(0)), text)


# Variant modifier phrases that distinguish different versions of the same base beer.
# These are checked as normalized (lowered, alphanumeric-only) substrings.
# Order: longer phrases first to allow greedy matching.
VARIANT_MODIFIERS: List[str] = sorted([
    "fresh hop", "fresh hopped",
    "barrel aged", "bourbon barrel aged", "rum barrel aged",
    "whiskey barrel aged", "wine barrel aged",
    "oak aged",
    "nitro",
    "cask",
    "double dry hopped", "triple dry hopped",
    "single dry hopped",
    "coffee", "vanilla", "coconut", "chocolate", "hazelnut",
    "mango", "guava", "passion fruit", "raspberry", "blueberry",
    "strawberry", "peach", "pineapple", "cherry",
    "lactose", "milkshake",
    "with brett", "brett",
    "reserve",
    "small batch",
    "collaboration",
    "on the rocks",
], key=len, reverse=True)

# Pre-computed normalized modifiers for fast comparison
_VARIANT_MODIFIERS_NORM: List[str] = [normalize_for_comparison(m) for m in VARIANT_MODIFIERS]


def extract_variant_modifiers(name: str) -> set:
    """
    Extracts variant modifier keywords found in a beer name.
    Returns a set of normalized modifier strings present in the name.
    """
    name_norm = normalize_for_comparison(name, expand_abbr=True)
    found: set = set()
    for mod_norm in _VARIANT_MODIFIERS_NORM:
        if mod_norm in name_norm:
            found.add(mod_norm)
    return found


def has_variant_mismatch(name_a: str, name_b: str) -> bool:
    """
    Returns True if the two beer names have different variant modifiers,
    indicating they are different variants of the same base beer.
    
    Example:
        "What Rough Beast" vs "Fresh Hop What Rough Beast" → True (mismatch)
        "What Rough Beast" vs "What Rough Beast" → False (no mismatch)
        "Fresh Hop What Rough Beast" vs "Fresh Hop What Rough Beast (2019)" → False
    """
    mods_a = extract_variant_modifiers(name_a)
    mods_b = extract_variant_modifiers(name_b)
    
    # Symmetric difference: modifiers in one but not the other
    diff = mods_a.symmetric_difference(mods_b)
    
    if diff:
        # Check if name_b (expected/shop name) has no modifiers and is a direct prefix of name_a
        # (e.g., "Whisky Sour" vs "Whisky Sour Barrel Aged Sour Ale") where the subtitle on Untappd just describes the style/aging of the base beer.
        if not mods_b and mods_a:
            norm_a = normalize_for_comparison(name_a)
            norm_b = normalize_for_comparison(name_b)
            if norm_a.startswith(norm_b) and len(norm_b) >= 4:
                remainder = norm_a[len(norm_b):]
                if any(m in remainder for m in mods_a) or any(s in remainder for s in ["sour", "ale", "stout", "ipa", "lager", "pilsner"]):
                    logger.debug(f"  [Variant] Subtitle match allowed: '{name_a}' extends base '{name_b}' with descriptive modifiers {mods_a}")
                    return False

        logger.debug(f"  [Variant] Modifier mismatch: '{name_a}' has {mods_a}, '{name_b}' has {mods_b}, diff={diff}")
        return True
    return False



def normalize_ordinals(text: str) -> str:
    """Converts ordinal numbers (11th, 2nd, etc.) to their English word equivalents."""
    def replace_ordinal(m: Match[str]) -> str:
        return _ORDINAL_MAP.get(m.group(0).lower(), m.group(0))
    return re.sub(r'\b\d+(?:st|nd|rd|th)\b', replace_ordinal, text, flags=re.IGNORECASE)


def strip_for_core_comparison(text: str) -> str:
    """Strips year, date markers, style suffixes, dashes, and punctuation for core name comparison."""
    # Remove year/date in parens or brackets like (2026), (2026.07), [26/07], (2026-07)
    text = re.sub(r'\s*[([（]\s*(?:20)?\d{2}(?:[./-]\d{1,2})?\s*[)\]）]\s*', ' ', text)
    # Remove standalone dates like 2026.07 at end
    text = re.sub(r'\s+(?:20)?\d{2}[./-]\d{1,2}$', ' ', text)
    # Remove em-dashes and en-dashes (common in Untappd names)
    text = re.sub(r'\s*[–—-]\s*', ' ', text)
    # Remove colons and everything after (often used for fruit additions in JP shops)
    text = re.sub(r':.*$', '', text)
    # Remove common beer style suffixes at end
    stripped = re.sub(
        r'\s+(?:Sake IPA|Sake Ale|Rice Ale|Sake|IPA|DIPA|TIPA|Hazy IPA|Double IPA|Triple IPA|NEIPA|West Coast IPA|'
        r'Session IPA|Stout|Imperial Stout|Pale Ale|Lager|Pilsner|Sour|Porter|Ale|Saison|Gose)\s*$',
        '', text, flags=re.IGNORECASE
    )
    stripped_clean = stripped.strip()
    # Avoid over-stripping when the style word is part of a short core title (e.g. "Whisky Sour", "Breakfast Stout")
    if len(stripped_clean) <= 3 or (len(stripped_clean.split()) == 1 and len(text.strip().split()) == 2 and len(stripped_clean) <= 4):
        return text.strip()
    return stripped_clean


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

    # Remove date/year markers like (2026.07), (2026/07), (26.07), [2026.07], (2026)
    name = re.sub(r'\s*[([（]\s*(?:20)?\d{2}(?:[./-]\d{1,2})?\s*[)\]）]\s*', ' ', name)
    name = re.sub(r'\s+(?:20)?\d{2}[./-]\d{1,2}$', '', name)

    # Remove #XX, Vol.X, Batch X patterns
    name = re.sub(r'#\d+', '', name)
    name = re.sub(r'Vol\.?\s*\d+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'Batch\s*\d+', '', name, flags=re.IGNORECASE)

    # Remove serve/container info in parentheses (e.g. (NITRO), (GAS), (CAN), (BOTTLE))
    name = re.sub(
        r'\s*\([^)]*(?:nitro|gas|can|bottle|keg)[^)]*\)',
        '', name, flags=re.IGNORECASE
    )
    # 日本語の括弧も考慮
    name = re.sub(
        r'\s*[（(][^）)]*(?:nitro|gas|can|bottle|keg|缶|瓶|生樽|窒素)[^）)]*[）)]',
        '', name, flags=re.IGNORECASE
    )

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
    name = re.sub(r'\s+(?:Sake IPA|Sake Ale|Rice Ale|Sake|Hazy IPA|Double IPA|Triple IPA|West Coast IPA|Session IPA|NEIPA|IPA|DIPA|TIPA|Stout|Porter|Lager|Pilsner|Saison|Ale)$', '', name, flags=re.IGNORECASE)

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

    suffixes: List[str] = [
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

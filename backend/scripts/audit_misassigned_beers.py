import re
import difflib
from typing import Dict, Any, List, Optional
from src.core.db import get_supabase_client
from src.services.store.brewery_manager import BreweryManager
from src.services.untappd.text_utils import normalize_for_comparison, COLLAB_SPLIT_PATTERN

supabase = get_supabase_client()
bm = BreweryManager()

def get_all_rows(table_name: str, filters: dict = None, select: str = "*", limit_total: int = 10000) -> List[Dict[str, Any]]:
    rows = []
    page_size = 1000
    offset = 0
    while offset < limit_total:
        q = supabase.table(table_name).select(select).range(offset, offset + page_size - 1)
        if filters:
            for k, v in filters.items():
                if v == "not.is.null":
                    q = q.not_.is_(k, "null")
                elif v == "is.null":
                    q = q.is_(k, "null")
                else:
                    q = q.eq(k, v)
        res = q.execute()
        data = res.data or []
        rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return rows

def check_mismatch(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_name = item.get("name") or ""
    shop = item.get("shop") or ""
    untappd_url = item.get("untappd_url") or ""
    untappd_b_name = item.get("untappd_brewery_name") or ""
    untappd_beer_name = item.get("untappd_beer_name") or ""
    
    if not untappd_url:
        return None

    # 1. Check Chouseiya specific: 【Beer/Brewery】
    m_chouseiya = re.search(r'【(.*?)/(.*?)】', raw_name)
    expected_b_chouseiya = None
    if m_chouseiya:
        b_raw = m_chouseiya.group(2).strip()
        b_clean = re.sub(r'[\(（].*?[\)）]', '', b_raw).strip()
        b_match = bm.find_brewery_in_text(b_clean)
        if b_match:
            expected_b_chouseiya = b_match.get("name_en")
        else:
            expected_b_chouseiya = b_clean

    # 2. Find brewery in raw name using BreweryManager
    detected_breweries = []
    # Check for collabs
    parts = re.split(r'\s*(?:[x×/]|collab(?:\s+w/)?)\s*', raw_name, flags=re.IGNORECASE)
    for p in parts:
        b_found = bm.find_brewery_in_text(p)
        if b_found and b_found.get("name_en") not in [b.get("name_en") for b in detected_breweries]:
            detected_breweries.append(b_found)
    
    # Also check full text
    full_found = bm.find_brewery_in_text(raw_name)
    if full_found and full_found.get("name_en") not in [b.get("name_en") for b in detected_breweries]:
        detected_breweries.append(full_found)

    # Evaluate Brewery Mismatch
    brewery_mismatch = False
    brewery_reason = ""
    
    # Extract slug from untappd_url (e.g. https://untappd.com/b/uchu-brewing-cosmic-zyme/6861575 -> uchu-brewing)
    slug_match = re.search(r'untappd\.com/b/([^/]+)/', untappd_url)
    slug = slug_match.group(1).lower() if slug_match else ""

    norm_untappd_b = normalize_for_comparison(untappd_b_name)

    if expected_b_chouseiya:
        norm_exp = normalize_for_comparison(expected_b_chouseiya)
        # Check if expected brewery matches untappd brewery or slug
        if norm_exp and not (norm_exp in norm_untappd_b or norm_untappd_b in norm_exp or norm_exp in slug.replace("-", "")):
            # Check aliases
            b_obj = bm.find_brewery_in_text(expected_b_chouseiya)
            aliases = (b_obj.get("aliases") or []) if b_obj else []
            alias_matched = any(normalize_for_comparison(a) in norm_untappd_b or normalize_for_comparison(a) in slug.replace("-", "") for a in aliases if len(a) >= 3)
            if not alias_matched:
                brewery_mismatch = True
                brewery_reason = f"Chouseiya brewery '{expected_b_chouseiya}' != Untappd brewery '{untappd_b_name}'"

    elif detected_breweries and not any(k in raw_name.lower() for k in ["set", "セット", "mix"]):
        # If we detected breweries, does untappd_b_name or slug match ANY of them?
        matched_any = False
        for b in detected_breweries:
            b_en = normalize_for_comparison(b.get("name_en") or "")
            b_jp = normalize_for_comparison(b.get("name_jp") or "")
            aliases = [normalize_for_comparison(a) for a in (b.get("aliases") or []) if len(a) >= 3]
            clean_slug = slug.replace("-", "")
            
            if b_en and (b_en in norm_untappd_b or norm_untappd_b in b_en or b_en in clean_slug):
                matched_any = True
                break
            if aliases and any(a in norm_untappd_b or a in clean_slug for a in aliases):
                matched_any = True
                break

        if not matched_any and len(detected_breweries) == 1:
            detected_name = detected_breweries[0].get("name_en")
            # Extra safety check: if detected_name is too generic (like "Two"), skip
            if len(detected_name) > 3:
                brewery_mismatch = True
                brewery_reason = f"Detected brewery '{detected_name}' != Untappd brewery '{untappd_b_name}' (slug: {slug})"

    # 3. Check Beer Name Mismatch
    # Extract english-like words from raw name
    # e.g. "COSMIC ZYME" -> ["cosmic", "zyme"]
    raw_ascii_tokens = set(re.findall(r'[a-zA-Z]{3,}', raw_name.lower()))
    untappd_tokens = set(re.findall(r'[a-zA-Z]{3,}', untappd_beer_name.lower()))
    
    # Remove common style/noise words
    noise = {"the", "and", "ipa", "dipa", "tipa", "ale", "sour", "stout", "lager", "pilsner", "hazy", "can", "bottle", "draft", "year", "aged"}
    raw_ascii_tokens -= noise
    untappd_tokens -= noise

    name_mismatch = False
    name_reason = ""
    if raw_ascii_tokens and untappd_tokens:
        common = raw_ascii_tokens & untappd_tokens
        if not common:
            # Check similarity of the whole string
            clean_raw = " ".join(sorted(raw_ascii_tokens))
            clean_unt = " ".join(sorted(untappd_tokens))
            ratio = difflib.SequenceMatcher(None, clean_raw, clean_unt).ratio()
            if ratio < 0.35:
                name_mismatch = True
                name_reason = f"No common words between '{raw_ascii_tokens}' and '{untappd_tokens}' (Untappd: {untappd_beer_name})"

    if brewery_mismatch or (name_mismatch and not any(k in raw_name.lower() for k in ["set", "セット", "mix", "パック"])):
        return {
            "shop": shop,
            "name": raw_name,
            "url": item.get("url"),
            "untappd_url": untappd_url,
            "untappd_beer": untappd_beer_name,
            "untappd_brewery": untappd_b_name,
            "brewery_mismatch": brewery_mismatch,
            "name_mismatch": name_mismatch,
            "reason": brewery_reason or name_reason,
            "stock_status": item.get("stock_status")
        }
    return None

def main():
    print("Loading in-stock beers from beer_info_view...")
    items = get_all_rows("beer_info_view", filters={"stock_status": "In Stock", "untappd_url": "not.is.null"}, limit_total=5000)
    print(f"Total in-stock with untappd: {len(items)}")

    suspicious = []
    for it in items:
        res = check_mismatch(it)
        if res:
            suspicious.append(res)

    print(f"\nFound {len(suspicious)} suspicious misassigned beers in In Stock items:")
    print("=" * 80)
    for idx, s in enumerate(suspicious, 1):
        print(f"{idx:2d}. [{s['shop']}] {s['name']}")
        print(f"    Current Untappd: {s['untappd_url']}")
        print(f"    Untappd Info: {s['untappd_brewery']} - {s['untappd_beer']}")
        print(f"    Reason: {s['reason']}")
        print("-" * 80)

if __name__ == "__main__":
    main()

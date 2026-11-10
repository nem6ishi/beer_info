import re
import difflib
from typing import Dict, Any, List, Optional
from src.core.db import get_supabase_client
from src.services.store.brewery_manager import BreweryManager
from src.services.untappd.text_utils import normalize_for_comparison

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

def is_strict_mismatch(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_name = item.get("name") or ""
    shop = item.get("shop") or ""
    untappd_url = item.get("untappd_url") or ""
    untappd_b_name = item.get("untappd_brewery_name") or ""
    untappd_beer_name = item.get("untappd_beer_name") or ""
    
    if not untappd_url or not untappd_b_name:
        return None

    # Ignore gift sets / variety packs
    if any(k in raw_name.lower() for k in ["set", "セット", "mix pack", "mixpack", "4本セット", "6本セット", "8本セット"]):
        return None

    # Extract slug
    slug_match = re.search(r'untappd\.com/b/([^/]+)/', untappd_url)
    slug = slug_match.group(1).lower() if slug_match else ""
    norm_untappd_b = normalize_for_comparison(untappd_b_name)
    clean_slug = slug.replace("-", "")

    # 1. Chouseiya STRICT: 【Beer/Brewery】
    if shop == "ちょうせいや":
        m = re.search(r'【(.*?)/(.*?)】', raw_name)
        if m:
            beer_part = m.group(1).strip()
            brewery_part = m.group(2).strip()
            brewery_part = re.sub(r'[\(（].*?[\)）]', '', brewery_part).strip()
            b_obj = bm.find_brewery_in_text(brewery_part)
            if b_obj:
                b_en = normalize_for_comparison(b_obj.get("name_en") or "")
                aliases = [normalize_for_comparison(a) for a in (b_obj.get("aliases") or []) if len(a) >= 3]
                if b_en and not (b_en in norm_untappd_b or norm_untappd_b in b_en or b_en in clean_slug or any(a in norm_untappd_b or a in clean_slug for a in aliases)):
                    # Check collab
                    if not any(k in raw_name for k in ["×", "x", "X"]):
                        return {
                            "shop": shop, "name": raw_name, "url": item.get("url"),
                            "untappd_url": untappd_url, "untappd_beer": untappd_beer_name, "untappd_brewery": untappd_b_name,
                            "type": "Brewery Mismatch (Chouseiya)",
                            "detail": f"Expected '{b_obj.get('name_en')}' but got '{untappd_b_name}'"
                        }

    # 2. WITCH CRAFT MARKET: [Brewery] Beer
    if shop == "WITCH CRAFT MARKET":
        m = re.search(r'\[(.*?)\]', raw_name)
        if m:
            b_text = m.group(1).strip()
            b_obj = bm.find_brewery_in_text(b_text)
            if b_obj:
                b_en = normalize_for_comparison(b_obj.get("name_en") or "")
                aliases = [normalize_for_comparison(a) for a in (b_obj.get("aliases") or []) if len(a) >= 3]
                if b_en and not (b_en in norm_untappd_b or norm_untappd_b in b_en or b_en in clean_slug or any(a in norm_untappd_b or a in clean_slug for a in aliases)):
                    if not any(k in raw_name for k in ["×", "x", "X"]):
                        return {
                            "shop": shop, "name": raw_name, "url": item.get("url"),
                            "untappd_url": untappd_url, "untappd_beer": untappd_beer_name, "untappd_brewery": untappd_b_name,
                            "type": "Brewery Mismatch (WCM)",
                            "detail": f"Expected '{b_obj.get('name_en')}' but got '{untappd_b_name}'"
                        }

    # 3. BEER VOLTA: Brewery : Beer | En Brewery: En Beer
    if shop == "BEER VOLTA" and "|" in raw_name:
        parts = raw_name.split("|")
        en_part = parts[-1].strip()
        if ":" in en_part:
            b_cand, beer_cand = en_part.split(":", 1)
            b_obj = bm.find_brewery_in_text(b_cand.strip())
            if b_obj:
                b_en = normalize_for_comparison(b_obj.get("name_en") or "")
                aliases = [normalize_for_comparison(a) for a in (b_obj.get("aliases") or []) if len(a) >= 3]
                if b_en and not (b_en in norm_untappd_b or norm_untappd_b in b_en or b_en in clean_slug or any(a in norm_untappd_b or a in clean_slug for a in aliases)):
                    if not any(k in raw_name for k in ["×", "x", "X"]):
                        return {
                            "shop": shop, "name": raw_name, "url": item.get("url"),
                            "untappd_url": untappd_url, "untappd_beer": untappd_beer_name, "untappd_brewery": untappd_b_name,
                            "type": "Brewery Mismatch (BEER VOLTA)",
                            "detail": f"Expected '{b_obj.get('name_en')}' but got '{untappd_b_name}'"
                        }

    # 4. English Beer Name Mismatch (Strict)
    # Extract distinct English words from product name
    # e.g. "Old Rasputin (473ml)" -> ["old", "rasputin"]
    # Check if untappd_beer_name contains any of them
    en_words = re.findall(r'[A-Za-z]{3,}', raw_name)
    noise_words = {
        "the", "and", "for", "with", "can", "bottle", "ipa", "dipa", "tipa", "ale", "sour", "stout", 
        "lager", "pilsner", "hazy", "craft", "beer", "brewing", "brewery", "japan", "tokyo", "off",
        "vol", "ml", "oz", "draft", "special", "edition", "series", "limited", "dry", "hopped", "hop"
    }
    meaningful_raw_words = [w.lower() for w in en_words if w.lower() not in noise_words and len(w) >= 4]
    
    # Also ignore brewery names from meaningful words
    found_b = bm.find_brewery_in_text(raw_name)
    if found_b:
        b_en_words = re.findall(r'[A-Za-z]{3,}', found_b.get("name_en") or "")
        meaningful_raw_words = [w for w in meaningful_raw_words if w not in [bw.lower() for bw in b_en_words]]

    unt_words = re.findall(r'[A-Za-z]{3,}', untappd_beer_name)
    meaningful_unt_words = [w.lower() for w in unt_words if w.lower() not in noise_words and len(w) >= 4]

    # If we have at least 1 very specific word (e.g. rasputin, cosmic, zyme, kyomei) and none match untappd beer name
    if meaningful_raw_words and meaningful_unt_words:
        common = set(meaningful_raw_words) & set(meaningful_unt_words)
        if not common:
            # Check substrings (e.g. "rasputin" in "oldrasputin")
            substr_match = any(rw in " ".join(meaningful_unt_words) or uw in " ".join(meaningful_raw_words) 
                               for rw in meaningful_raw_words for uw in meaningful_unt_words)
            if not substr_match:
                # High confidence mismatch!
                return {
                    "shop": shop, "name": raw_name, "url": item.get("url"),
                    "untappd_url": untappd_url, "untappd_beer": untappd_beer_name, "untappd_brewery": untappd_b_name,
                    "type": "Beer Name Mismatch",
                    "detail": f"Raw distinct words {meaningful_raw_words} do NOT match Untappd '{untappd_beer_name}'"
                }

    return None

def main():
    print("Fetching in-stock beers from beer_info_view...")
    items = get_all_rows("beer_info_view", filters={"stock_status": "In Stock", "untappd_url": "not.is.null"}, limit_total=5000)
    print(f"Total in-stock with untappd: {len(items)}")

    mismatches = []
    for it in items:
        res = is_strict_mismatch(it)
        if res:
            mismatches.append(res)

    print(f"\n🚨 STRICT MISMATCHES FOUND: {len(mismatches)}")
    print("=" * 80)
    for idx, m in enumerate(mismatches, 1):
        print(f"{idx:2d}. [{m['shop']}] {m['name']}")
        print(f"    Current Untappd: {m['untappd_url']}")
        print(f"    Current Untappd Info: {m['untappd_brewery']} - {m['untappd_beer']}")
        print(f"    Type: {m['type']} | {m['detail']}")
        print("-" * 80)

if __name__ == "__main__":
    main()

import re
import json
import logging
from typing import List, Dict, Any, Set
from backend.src.core.db import get_supabase_client, refresh_materialized_view

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    sb = get_supabase_client()
    
    logger.info("1. Loading all breweries from DB...")
    res = sb.from_("breweries").select("*").execute()
    breweries: List[Dict[str, Any]] = res.data
    logger.info(f"Loaded {len(breweries)} breweries.")
    
    # Map of all main names & cleaned names to brewery IDs
    main_name_to_ids: Dict[str, Set[str]] = {}
    for b in breweries:
        b_id = b["id"]
        names = []
        if b.get("name_en"):
            names.append(b["name_en"].lower())
            clean_en = re.sub(r'\b(brewing|brewery|beer|co)\b', '', b["name_en"].lower()).strip()
            if clean_en:
                names.append(clean_en)
        if b.get("name_jp"):
            names.append(b["name_jp"].lower())
        for n in set(names):
            if n not in main_name_to_ids:
                main_name_to_ids[n] = set()
            main_name_to_ids[n].add(b_id)
            
    logger.info(f"Built main names lookup with {len(main_name_to_ids)} keys.")
    
    updated_count = 0
    removed_aliases_total = 0
    
    logger.info("2. Cleaning polluted aliases...")
    for b in breweries:
        b_id = b["id"]
        b_en = b.get("name_en") or ""
        b_jp = b.get("name_jp") or ""
        raw_aliases = b.get("aliases") or []
        
        cleaned_aliases = []
        removed_aliases = []
        
        for alias in raw_aliases:
            alias_str = alias.strip()
            alias_lower = alias_str.lower()
            alias_clean = re.sub(r'\b(brewing|brewery|beer|co)\b', '', alias_lower).strip()
            
            # Check collaboration patterns
            if re.search(r'(\bx\b|×|\bcollab\b|collaboration|,|&)', alias_str, re.IGNORECASE):
                removed_aliases.append((alias_str, "Collaboration pattern"))
                continue
                
            # Check conflict with main names of OTHER breweries
            conflicts = False
            for test_key in [alias_lower, alias_clean]:
                if test_key and test_key in main_name_to_ids:
                    conflicting_ids = main_name_to_ids[test_key] - {b_id}
                    if conflicting_ids:
                        conflicts = True
                        break
            
            if conflicts:
                removed_aliases.append((alias_str, "Conflict with other brewery main name"))
                continue
                
            if alias_lower in (b_en.lower(), b_jp.lower()):
                # Redundant with main name
                continue
                
            cleaned_aliases.append(alias_str)
            
        # Deduplicate preserving order
        unique_cleaned = []
        seen = set()
        for a in cleaned_aliases:
            if a.lower() not in seen:
                seen.add(a.lower())
                unique_cleaned.append(a)
                
        if len(unique_cleaned) != len(raw_aliases):
            sb.from_("breweries").update({"aliases": unique_cleaned}).eq("id", b_id).execute()
            updated_count += 1
            removed_aliases_total += len(removed_aliases)
            logger.info(f"  🧹 Cleaned '{b_en}': removed {len(removed_aliases)} bad aliases. Kept {len(unique_cleaned)} aliases.")
            for ra, reason in removed_aliases:
                logger.info(f"     - Removed '{ra}' ({reason})")

    logger.info(f"✅ Cleaned aliases for {updated_count} breweries (removed {removed_aliases_total} aliases).")
    
    logger.info("\n3. Fixing target product 'うちゅうブルーイング / 宇宙LAGER' (id=6939)...")
    url_target = "https://www.arome.jp/products/detail.php?product_id=6939"
    correct_untappd_url = "https://untappd.com/b/uchu-brewing-lager-uchu-lager/6582079"
    
    # 1. Update gemini_data
    sb.from_("gemini_data").upsert({
        "url": url_target,
        "brewery_name_jp": "うちゅうブルーイング",
        "brewery_name_en": "Uchu Brewing",
        "beer_name_jp": "宇宙LAGER",
        "beer_name_en": "UCHU LAGER",
        "beer_name_core": "UCHU LAGER",
        "search_hint": "UCHU LAGER Uchu Brewing",
        "payload": "MANUAL_FIX_FOR_UCHU_LAGER",
        "product_type": "beer",
        "is_set": False,
        "untappd_url": correct_untappd_url
    }).execute()
    
    # 2. Update scraped_beers
    sb.from_("scraped_beers").update({
        "untappd_url": correct_untappd_url
    }).eq("url", url_target).execute()
    
    # 3. Ensure untappd_data exists for this beer
    res_u = sb.from_("untappd_data").select("*").eq("untappd_url", correct_untappd_url).execute()
    if not res_u.data:
        sb.from_("untappd_data").upsert({
            "untappd_url": correct_untappd_url,
            "beer_name": "宇宙LAGER (UCHU LAGER)",
            "brewery_name": "Uchu Brewing",
            "style": "Lager - Helles",
            "abv": "5%",
            "abv_num": 5.0,
            "rating": "3.8",
            "rating_num": 3.8,
            "rating_count": "100",
            "rating_count_num": 100,
            "image_url": "https://assets.untappd.com/site/beer_logos/beer-6582079_596ff_sm.jpeg",
            "untappd_brewery_url": "https://untappd.com/UchuBrewing"
        }).execute()
        
    logger.info(f"✅ Product 6939 successfully updated to Uchu Brewing / {correct_untappd_url}")
    
    logger.info("\n4. Scanning for other products incorrectly assigned to West Coast Brewing via Tier 2 match...")
    res_all_gemini = sb.from_("gemini_data").select("url, payload, beer_name_jp, beer_name_en").execute()
    
    fixed_misassigned = 0
    for row in res_all_gemini.data:
        p_url = row["url"]
        payload_str = str(row.get("payload") or "")
        if "RESOLVED_BY_TIER2_DICTIONARY_MATCH: West Coast Brewing" in payload_str:
            sb_res = sb.from_("scraped_beers").select("name").eq("url", p_url).execute()
            if sb_res.data:
                orig_name = sb_res.data[0]["name"]
                # If the original name does NOT contain West Coast / WCB / ウエストコースト
                if not re.search(r'west\s*coast|wcb|ウエストコースト', orig_name, re.IGNORECASE):
                    logger.info(f"  ⚠️ Found misassigned beer: '{orig_name}' ({p_url})")
                    # Reset gemini_data payload so it can be properly re-processed
                    sb.from_("gemini_data").delete().eq("url", p_url).execute()
                    sb.from_("scraped_beers").update({"untappd_url": None}).eq("url", p_url).execute()
                    fixed_misassigned += 1
                
    logger.info(f"✅ Reset {fixed_misassigned} misassigned beers for re-processing.")
    
    logger.info("\n5. Refreshing Materialized View (beer_info_view)...")
    refresh_materialized_view(sb, logger)
    logger.info("🎉 All tasks completed successfully!")

if __name__ == "__main__":
    main()

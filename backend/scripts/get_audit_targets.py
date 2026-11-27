"""
Helper script for Daily Beer Enrichment & Quality Audit.
Outputs target candidates and automated anomaly detections for In Stock items:
1. Unenriched in-stock items (top priority)
2. Automated quality anomaly checks:
   - Year mismatches (vintage year in shop title vs Untappd beer name)
   - Duplicate Untappd IDs with differing URL slugs (breaks grouping)
   - Suspected product_type misclassifications (e.g., beers marked as glass/set)
   - Style / Brewery / Collab mismatches (e.g., Hazy IPA linked to Sour, collab swapped)
3. Cross-store linkable candidates (unlinked in-stock beers matching another shop's linked beer)
4. Recently added in-stock items (past 48-72h) for sanity check & correction
5. Unlinked in-stock beers needing Untappd investigation
6. Rolling audit of existing items (oldest fetched)
"""
import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from backend.src.core.db import get_supabase_client, sync_execute


def _fetch_all_in_stock(sb) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        res = sync_execute(
            sb.table("beer_info_view")
            .select(
                "url, name, shop, first_seen, stock_status, untappd_enriched_at, "
                "untappd_fetched_at, untappd_url, untappd_beer_name, untappd_brewery_name, "
                "untappd_rating, product_type, is_set"
            )
            .eq("stock_status", "In Stock")
            .range(offset, offset + page_size - 1)
        )
        data = res.data or []
        rows.extend(data)
        if len(data) < page_size:
            break
        offset += page_size
    return rows


def _detect_year_mismatches(linked_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mismatches = []
    for r in linked_rows:
        raw = r.get("name") or ""
        cleaned_raw = re.sub(r"(期限|賞味期限|best before|bb)[^\s】\)]*20[12]\d", "", raw, flags=re.I)
        cleaned_raw = re.sub(r"20[12]\d[\./年]\d{1,2}", "", cleaned_raw)
        raw_years = set(re.findall(r"\b(201[5-9]|202[0-9])\b", cleaned_raw))
        unt_years = set(re.findall(r"\b(201[5-9]|202[0-9])\b", r.get("untappd_beer_name") or ""))
        if raw_years and unt_years and raw_years != unt_years:
            mismatches.append(
                {
                    "shop": r.get("shop"),
                    "name": raw,
                    "url": r.get("url"),
                    "untappd_url": r.get("untappd_url"),
                    "untappd_brewery_name": r.get("untappd_brewery_name"),
                    "untappd_beer_name": r.get("untappd_beer_name"),
                    "raw_years": sorted(raw_years),
                    "untappd_years": sorted(unt_years),
                }
            )
    return mismatches


def _detect_duplicate_untappd_ids(linked_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    id_to_items: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for r in linked_rows:
        u = r.get("untappd_url") or ""
        m = re.search(r"/(\d+)/?$", u)
        if m:
            id_to_items[m.group(1)][u].append(
                {"shop": r.get("shop"), "name": r.get("name"), "url": r.get("url")}
            )

    duplicates = []
    for bid, url_map in id_to_items.items():
        if len(url_map) > 1:
            duplicates.append(
                {
                    "untappd_id": bid,
                    "variants": [
                        {"untappd_url": u, "count": len(items), "items": items}
                        for u, items in sorted(url_map.items(), key=lambda x: -len(x[1]))
                    ],
                }
            )
    return duplicates


def _detect_misclassified_non_beers(in_stock_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect unlinked items marked as glass/set/other that look like single beers."""
    suspects = []
    glass_keywords = ["glass", "グラス", "ジョッキ", "タンブラー", "goblet", "ゴブレット", "chalice", "チャリス", "mug", "マグ", "glazen", "パイント"]
    set_keywords = ["set", "セット", "飲み比べ", "本セット", "種セット", "mix pack", "mixpack", "pack", "アソート", "詰め合わせ"]

    for r in in_stock_rows:
        if r.get("untappd_url"):
            continue
        ptype = r.get("product_type")
        if ptype in ("beer", None):
            continue
        name = r.get("name") or ""
        name_lower = name.lower()

        # Catch "グラスプ" (Grasp) mistakenly matched as "グラス" (Glass)
        if ptype == "glass":
            cleaned = name_lower.replace("グラスプ", "")
            has_glass_word = any(k in cleaned for k in glass_keywords)
            if not has_glass_word:
                suspects.append(
                    {
                        "shop": r.get("shop"),
                        "name": name,
                        "url": r.get("url"),
                        "product_type": ptype,
                        "is_set": r.get("is_set"),
                        "reason": "product_type=glass だがグラス関連語が見当たりません",
                    }
                )
        elif ptype == "set" and not r.get("is_set"):
            has_set_word = any(k in name_lower for k in set_keywords)
            if not has_set_word:
                suspects.append(
                    {
                        "shop": r.get("shop"),
                        "name": name,
                        "url": r.get("url"),
                        "product_type": ptype,
                        "is_set": r.get("is_set"),
                        "reason": "product_type=set かつ is_set=False でセット関連語が見当たりません",
                    }
                )
    return suspects


def _detect_style_or_collab_anomalies(linked_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect obvious style contradictions (e.g., Hazy IPA linked to Sour, Sour linked to Saison)."""
    anomalies = []
    for r in linked_rows:
        name = r.get("name") or ""
        name_l = name.lower()
        u_beer = r.get("untappd_beer_name") or ""
        u_beer_l = u_beer.lower()
        u_brew = r.get("untappd_brewery_name") or ""

        # 1. Hazy / DIPA / IPA explicitly in title, but Untappd beer name explicitly says (Sour) / Sour
        if any(k in name_l for k in ["hazy", "dipa", "ヘイジーダブル"]) and not any(k in name_l for k in ["sour", "サワー"]):
            if any(k in u_beer_l for k in ["(sour)", "sour ale", "peach sour", "fruited sour"]):
                anomalies.append(
                    {
                        "shop": r.get("shop"),
                        "name": name,
                        "url": r.get("url"),
                        "untappd_url": r.get("untappd_url"),
                        "untappd_brewery_name": u_brew,
                        "untappd_beer_name": u_beer,
                        "reason": "商品名は Hazy/DIPA だが Untappd 名が Sour",
                    }
                )
        # 2. Sour explicitly in title, but Untappd beer name says Saison (and title doesn't say Saison)
        if any(k in name_l for k in ["sour", "サワー"]) and not any(k in name_l for k in ["saison", "セゾン"]):
            if "saison" in u_beer_l and "sour" not in u_beer_l:
                anomalies.append(
                    {
                        "shop": r.get("shop"),
                        "name": name,
                        "url": r.get("url"),
                        "untappd_url": r.get("untappd_url"),
                        "untappd_brewery_name": u_brew,
                        "untappd_beer_name": u_beer,
                        "reason": "商品名は Sour だが Untappd 名が Saison",
                    }
                )
        # 3. "Window to WCB" vs "Window to VERTERE" or similar swapped collab titles
        m_raw_to = re.search(r"window\s+to\s+([a-z0-9]+)", name_l)
        m_unt_to = re.search(r"window\s+to\s+([a-z0-9]+)", u_beer_l)
        if m_raw_to and m_unt_to and m_raw_to.group(1) != m_unt_to.group(1):
            anomalies.append(
                {
                    "shop": r.get("shop"),
                    "name": name,
                    "url": r.get("url"),
                    "untappd_url": r.get("untappd_url"),
                    "untappd_brewery_name": u_brew,
                    "untappd_beer_name": u_beer,
                    "reason": f"コラボ対象不一致: raw='window to {m_raw_to.group(1)}' vs untappd='window to {m_unt_to.group(1)}'",
                }
            )
    return anomalies


def _normalize_tokens(text: str) -> set:
    noise = {
        "the", "and", "for", "with", "can", "bottle", "ipa", "dipa", "tipa", "ale",
        "sour", "stout", "lager", "pilsner", "hazy", "craft", "beer", "brewing",
        "brewery", "company", "nyc", "japan", "tokyo", "collab", "473ml", "355ml",
        "350ml", "500ml", "750ml", "330ml", "west", "coast", "double", "imperial",
        "pale", "fresh", "hop", "edition", "limited", "dry", "hopped", "ddh", "tdh",
        "festbier", "saison", "blonde", "porter", "gose", "helles", "bock", "tripel",
    }
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return {w for w in cleaned.split() if len(w) >= 3 and w not in noise}


def _extract_batch_tags(text: str) -> set:
    return set(re.findall(r"(?:\bv-\d+\b|#\d+\b)", (text or "").lower()))


def _detect_cross_store_candidates(
    unlinked_beers: List[Dict[str, Any]], linked_rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Find unlinked in-stock beers that strongly match an already-linked beer in another shop."""
    # Deduplicate linked catalog by untappd_url
    catalog: Dict[str, Dict[str, Any]] = {}
    for r in linked_rows:
        u = r.get("untappd_url")
        if u and u not in catalog:
            beer_name = r.get("untappd_beer_name") or ""
            brew_name = r.get("untappd_brewery_name") or ""
            catalog[u] = {
                "untappd_url": u,
                "untappd_beer_name": beer_name,
                "untappd_brewery_name": brew_name,
                "beer_tokens": _normalize_tokens(beer_name),
                "brew_tokens": _normalize_tokens(brew_name),
                "batch_tags": _extract_batch_tags(beer_name),
                "sample_shop": r.get("shop"),
            }

    candidates = []
    for item in unlinked_beers:
        raw = item.get("name") or ""
        raw_l = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
        raw_tokens = _normalize_tokens(raw)
        raw_batches = _extract_batch_tags(raw)
        if not raw_tokens:
            continue

        best_match = None
        best_score = 0.0
        for entry in catalog.values():
            b_tokens = entry["beer_tokens"]
            if not b_tokens:
                continue
            if raw_batches and entry["batch_tags"] and raw_batches != entry["batch_tags"]:
                continue
            overlap = raw_tokens & b_tokens
            if not overlap:
                continue
            # Require either full beer_name substring match or strong token overlap + brewery token match
            beer_norm = re.sub(r"[^a-z0-9]+", " ", entry["untappd_beer_name"].lower()).strip()
            exact_sub = len(beer_norm) >= 5 and beer_norm in raw_l
            brew_overlap = bool(raw_tokens & entry["brew_tokens"])
            coverage = len(overlap) / len(b_tokens)

            score = 0.0
            if exact_sub and brew_overlap:
                score = 1.0 + len(overlap) * 0.1
            elif exact_sub and len(beer_norm) >= 8:
                score = 0.9 + len(overlap) * 0.05
            elif brew_overlap and coverage >= 0.75 and len(overlap) >= 2:
                score = 0.8 + coverage * 0.1
            elif brew_overlap and len(overlap) >= 4:
                # Truncated long titles (e.g. "THIS IPA DOESN'T CARE ABOUT YOU...")
                score = 0.85 + len(overlap) * 0.02

            if score > best_score:
                best_score = score
                best_match = entry

        if best_match and best_score >= 0.8:
            candidates.append(
                {
                    "shop": item.get("shop"),
                    "name": raw,
                    "url": item.get("url"),
                    "suggested_untappd_url": best_match["untappd_url"],
                    "suggested_brewery": best_match["untappd_brewery_name"],
                    "suggested_beer": best_match["untappd_beer_name"],
                    "matched_from_shop": best_match["sample_shop"],
                    "confidence": round(min(best_score, 1.0), 2),
                }
            )
    return candidates


def get_audit_targets(
    limit_unenriched: int = 30,
    limit_recent: int = 30,
    limit_rolling: int = 5,
    limit_unlinked: int = 20,
) -> Dict[str, Any]:
    sb = get_supabase_client()
    now = datetime.now(timezone.utc)

    in_stock = _fetch_all_in_stock(sb)
    linked = [r for r in in_stock if r.get("untappd_url")]
    unenriched = sorted(
        [r for r in in_stock if not r.get("untappd_enriched_at")],
        key=lambda x: x.get("first_seen") or "",
        reverse=True,
    )[:limit_unenriched]

    # Recently added/enriched in-stock items (past 48 hours, prioritizing newly added)
    recent_cutoff = (now - timedelta(days=2)).isoformat()
    recent_new = sorted(
        [
            r
            for r in linked
            if (r.get("first_seen") or "") >= recent_cutoff
        ],
        key=lambda x: x.get("first_seen") or "",
        reverse=True,
    )[:limit_recent]

    # Rolling audit: oldest untappd_fetched_at
    rolling_candidates = sorted(
        [r for r in linked if r.get("product_type") in ("beer", None)],
        key=lambda x: (x.get("untappd_fetched_at") is not None, x.get("untappd_fetched_at") or ""),
    )[:limit_rolling]

    # Unlinked beers (beer or null, not set)
    all_unlinked_beers = [
        r
        for r in in_stock
        if not r.get("untappd_url")
        and r.get("product_type") in ("beer", None)
        and not r.get("is_set")
    ]
    unlinked_candidates = sorted(
        all_unlinked_beers,
        key=lambda x: (x.get("untappd_enriched_at") is not None, x.get("untappd_enriched_at") or ""),
    )[:limit_unlinked]

    # Automated anomaly checks
    year_mismatches = _detect_year_mismatches(linked)
    duplicate_untappd_ids = _detect_duplicate_untappd_ids(linked)
    misclassified_non_beers = _detect_misclassified_non_beers(in_stock)
    style_collab_anomalies = _detect_style_or_collab_anomalies(linked)
    cross_store_candidates = _detect_cross_store_candidates(all_unlinked_beers, linked)

    return {
        "timestamp": now.isoformat(),
        "summary": {
            "total_in_stock": len(in_stock),
            "linked": len(linked),
            "link_rate_pct": round(len(linked) / len(in_stock) * 100, 1) if in_stock else 0.0,
            "unenriched": len(unenriched),
            "unlinked_beers_total": len(all_unlinked_beers),
        },
        "unenriched": unenriched,
        "anomalies": {
            "year_mismatches": year_mismatches,
            "duplicate_untappd_ids": duplicate_untappd_ids,
            "misclassified_non_beers": misclassified_non_beers,
            "style_collab_anomalies": style_collab_anomalies,
        },
        "cross_store_candidates": cross_store_candidates,
        "recent_enriched_to_verify": recent_new,
        "rolling_audit_candidates": rolling_candidates,
        "unlinked_candidates": unlinked_candidates,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch daily audit targets & automated anomaly checks")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    targets = get_audit_targets()

    if args.json:
        print(json.dumps(targets, ensure_ascii=False, indent=2))
        return

    s = targets["summary"]
    print("=" * 75)
    print("🔍 DAILY BEER AUDIT & ENRICHMENT TARGETS")
    print(
        f"   In Stock: {s['total_in_stock']} | Linked: {s['linked']} ({s['link_rate_pct']}%) | "
        f"Unenriched: {s['unenriched']} | Unlinked Beers: {s['unlinked_beers_total']}"
    )
    print("=" * 75)

    # 1. Unenriched
    unenriched = targets["unenriched"]
    print(f"\n1. 未エンリッチ商品 (最優先) [{len(unenriched)} 件]:")
    if unenriched:
        for i, item in enumerate(unenriched, 1):
            print(f"   [{i}] ({item['shop']}) {item['name']} | URL: {item['url']}")
    else:
        print("   ✨ 未エンリッチ商品はありません。")

    # 2. Automated Anomalies
    an = targets["anomalies"]
    total_anomalies = (
        len(an["year_mismatches"])
        + len(an["duplicate_untappd_ids"])
        + len(an["misclassified_non_beers"])
        + len(an["style_collab_anomalies"])
    )
    print(f"\n2. 自動検知された異常・要是正項目 [{total_anomalies} 件]:")

    if an["style_collab_anomalies"]:
        print(f"   [2a] スタイル・コラボ不一致 [{len(an['style_collab_anomalies'])} 件]:")
        for i, x in enumerate(an["style_collab_anomalies"], 1):
            print(f"     ({i}) [{x['shop']}] {x['name']}")
            print(f"         -> 現状: [{x['untappd_brewery_name']}] {x['untappd_beer_name']} ({x['untappd_url']})")
            print(f"         -> 理由: {x['reason']} | shop_url: {x['url']}")

    if an["year_mismatches"]:
        print(f"   [2b] ヴィンテージ・年号不一致 [{len(an['year_mismatches'])} 件]:")
        for i, x in enumerate(an["year_mismatches"], 1):
            print(f"     ({i}) [{x['shop']}] {x['name']}")
            print(f"         -> 現状: [{x['untappd_brewery_name']}] {x['untappd_beer_name']} (raw={x['raw_years']} vs untappd={x['untappd_years']})")
            print(f"         -> shop_url: {x['url']} | untappd_url: {x['untappd_url']}")

    if an["misclassified_non_beers"]:
        print(f"   [2c] product_type 誤分類疑い (非ビール扱いだがビール候補) [{len(an['misclassified_non_beers'])} 件]:")
        for i, x in enumerate(an["misclassified_non_beers"], 1):
            print(f"     ({i}) [{x['shop']}] {x['name']} (type={x['product_type']}, is_set={x['is_set']})")
            print(f"         -> 理由: {x['reason']} | shop_url: {x['url']}")

    if an["duplicate_untappd_ids"]:
        print(f"   [2d] 同一 Untappd ID の URL スラグ不一致 [{len(an['duplicate_untappd_ids'])} 件]:")
        for i, x in enumerate(an["duplicate_untappd_ids"], 1):
            print(f"     ({i}) ID={x['untappd_id']}:")
            for v in x["variants"]:
                print(f"         - ({v['count']}件) {v['untappd_url']}")
                for it in v["items"]:
                    print(f"             * [{it['shop']}] {it['name']} ({it['url']})")

    if total_anomalies == 0:
        print("   ✨ 自動検知された異常はありません。")

    # 3. Cross-store linkable candidates
    cross = targets["cross_store_candidates"]
    print(f"\n3. 他ショップ既登録URLからの横展開候補 [{len(cross)} 件]:")
    if cross:
        for i, x in enumerate(cross, 1):
            print(f"   [{i}] ({x['shop']}) {x['name']}")
            print(f"       -> 候補: [{x['suggested_brewery']}] {x['suggested_beer']} (from {x['matched_from_shop']})")
            print(f"       -> untappd_url: {x['suggested_untappd_url']} | shop_url: {x['url']}")
    else:
        print("   ✨ 横展開候補はありません。")

    # 4. Recent newly added items
    recent = targets["recent_enriched_to_verify"]
    print(f"\n4. 直近48時間の新規追加・紐付け済み商品の目視検証対象 [{len(recent)} 件]:")
    if recent:
        for i, item in enumerate(recent, 1):
            u_beer = item.get("untappd_beer_name") or "---"
            u_brewery = item.get("untappd_brewery_name") or "---"
            print(f"   [{i}] ({item['shop']}) {item['name']}")
            print(f"       -> Untappd: [{u_brewery}] {u_beer} | {item.get('untappd_url')}")
    else:
        print("   ✨ 直近の対象はありません。")

    # 5. Unlinked beers
    unlinked = targets["unlinked_candidates"]
    print(f"\n5. Untappd未紐付け在庫ビール (調査・登録確認対象) [{len(unlinked)}/{s['unlinked_beers_total']} 件]:")
    if unlinked:
        for i, item in enumerate(unlinked, 1):
            enriched = item.get("untappd_enriched_at") or "未調査"
            print(f"   [{i}] ({item['shop']}) {item['name']}")
            print(f"       -> 調査状況: {enriched} | URL: {item.get('url')}")
    else:
        print("   ✨ 未紐付けビールはありません。")

    # 6. Rolling audit
    rolling = targets["rolling_audit_candidates"]
    print(f"\n6. 既存データのローリング巡回監査対象 [{len(rolling)} 件]:")
    if rolling:
        for i, item in enumerate(rolling, 1):
            u_beer = item.get("untappd_beer_name") or "---"
            u_brewery = item.get("untappd_brewery_name") or "---"
            fetched = item.get("untappd_fetched_at") or "未取得"
            print(f"   [{i}] ({item['shop']}) {item['name']}")
            print(f"       -> 現状: [{u_brewery}] {u_beer} (最終取得: {fetched}) | {item.get('untappd_url')}")
    else:
        print("   ✨ 監査対象はありません。")
    print("=" * 75)


if __name__ == "__main__":
    main()

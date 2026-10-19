"""
Helper script for Hourly Beer Enrichment & Quality Audit.
Outputs target candidates for:
1. Unenriched in-stock items (top priority)
2. Recently added/enriched in-stock items (sanity check & correction)
3. Rolling audit of existing items (oldest fetched or unlinked beers, 5-10 items)
"""
import json
import argparse
from datetime import datetime, timezone, timedelta
from backend.src.core.db import get_supabase_client

def get_audit_targets(limit_unenriched: int = 20, limit_recent: int = 5, limit_rolling: int = 5):
    sb = get_supabase_client()
    now = datetime.now(timezone.utc)

    # 1. Unenriched in-stock items
    unenriched_res = sb.table('scraped_beers') \
        .select('url, name, shop, first_seen, stock_status') \
        .eq('stock_status', 'In Stock') \
        .is_('untappd_enriched_at', 'null') \
        .order('first_seen', desc=True) \
        .limit(limit_unenriched) \
        .execute()
    unenriched = unenriched_res.data or []

    # 2. Recently added/enriched in-stock items (past 48 hours)
    recent_cutoff = (now - timedelta(days=2)).isoformat()
    recent_res = sb.table('beer_info_view') \
        .select('url, name, shop, first_seen, untappd_enriched_at, untappd_url, untappd_beer_name, untappd_brewery_name, untappd_rating, product_type') \
        .eq('stock_status', 'In Stock') \
        .not_.is_('untappd_url', 'null') \
        .gte('untappd_enriched_at', recent_cutoff) \
        .order('untappd_enriched_at', desc=True) \
        .limit(limit_recent) \
        .execute()
    recent_enriched = recent_res.data or []

    # 3. Rolling audit: in-stock beers with oldest untappd_fetched_at (refresh candidates)
    rolling_res = sb.table('beer_info_view') \
        .select('url, name, shop, first_seen, untappd_fetched_at, untappd_url, untappd_beer_name, untappd_brewery_name, untappd_rating, product_type') \
        .eq('stock_status', 'In Stock') \
        .not_.is_('untappd_url', 'null') \
        .or_('product_type.eq.beer,product_type.is.null') \
        .order('untappd_fetched_at', desc=False, nullsfirst=True) \
        .limit(limit_rolling) \
        .execute()
    rolling_candidates = rolling_res.data or []

    # 4. Unlinked beers needing Untappd investigation (uninspected first, then rolling oldest)
    unlinked_res = sb.table('beer_info_view') \
        .select('url, name, shop, first_seen, untappd_url, untappd_enriched_at, product_type') \
        .eq('stock_status', 'In Stock') \
        .is_('untappd_url', 'null') \
        .or_('product_type.eq.beer,product_type.is.null') \
        .order('untappd_enriched_at', desc=False, nullsfirst=True) \
        .limit(5) \
        .execute()
    unlinked_candidates = unlinked_res.data or []

    return {
        "timestamp": now.isoformat(),
        "unenriched": unenriched,
        "recent_enriched_to_verify": recent_enriched,
        "rolling_audit_candidates": rolling_candidates,
        "unlinked_candidates": unlinked_candidates
    }

def main():
    parser = argparse.ArgumentParser(description="Fetch hourly audit targets")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    targets = get_audit_targets()

    if args.json:
        print(json.dumps(targets, ensure_ascii=False, indent=2))
    else:
        print("=" * 70)
        print("🔍 HOURLY BEER AUDIT & ENRICHMENT TARGETS")
        print("=" * 70)

        unenriched = targets["unenriched"]
        print(f"\n1. 未エンリッチ商品 (最優先) [{len(unenriched)} 件]:")
        if unenriched:
            for i, item in enumerate(unenriched, 1):
                print(f"   [{i}] ({item['shop']}) {item['name']} | URL: {item['url']}")
        else:
            print("   ✨ 未エンリッチ商品はありません。")

        recent = targets["recent_enriched_to_verify"]
        print(f"\n2. 直近追加・エンリッチ商品の確認・検証対象 [{len(recent)} 件]:")
        if recent:
            for i, item in enumerate(recent, 1):
                u_beer = item.get('untappd_beer_name') or '---'
                u_brewery = item.get('untappd_brewery_name') or '---'
                rating = item.get('untappd_rating') or '---'
                print(f"   [{i}] ({item['shop']}) {item['name']}\n       -> Untappd: [{u_brewery}] {u_beer} (Rating: {rating})\n       -> URL: {item.get('untappd_url')}")
        else:
            print("   ✨ 直近の対象はありません。")

        rolling = targets["rolling_audit_candidates"]
        print(f"\n3. 既存データのローリング巡回監査・情報更新対象 [{len(rolling)} 件]:")
        if rolling:
            for i, item in enumerate(rolling, 1):
                u_beer = item.get('untappd_beer_name') or '---'
                u_brewery = item.get('untappd_brewery_name') or '---'
                fetched = item.get('untappd_fetched_at') or '未取得'
                print(f"   [{i}] ({item['shop']}) {item['name']}\n       -> 現状: [{u_brewery}] {u_beer} (最終取得: {fetched})\n       -> URL: {item.get('untappd_url')}")
        else:
            print("   ✨ 監査対象はありません。")

        unlinked = targets["unlinked_candidates"]
        print(f"\n4. Untappd未紐付け在庫ビール (調査・登録確認対象) [{len(unlinked)} 件]:")
        if unlinked:
            for i, item in enumerate(unlinked, 1):
                enriched = item.get('untappd_enriched_at') or '未調査'
                print(f"   [{i}] ({item['shop']}) {item['name']}\n       -> 調査状況: {enriched}\n       -> URL: {item.get('url')}")
        else:
            print("   ✨ 未紐付けビールはありません。")
        print("=" * 70)

if __name__ == '__main__':
    main()

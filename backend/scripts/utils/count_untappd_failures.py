import asyncio
from collections import Counter
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from backend.src.core.db import get_supabase_client


def _fetch_all_unresolved(supabase):
    rows = []
    page_size = 1000
    offset = 0
    while True:
        res = (
            supabase.table('untappd_search_failures')
            .select('product_url, failure_reason, last_failed_at')
            .eq('resolved', False)
            .order('id')
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


async def main():
    supabase = get_supabase_client()
    rows = _fetch_all_unresolved(supabase)
    total_failures = len(rows)

    print("📊 Untappd 検索失敗の統計 (未解決のみ)")
    print("=" * 50)
    print(f"合計失敗数: {total_failures} 件")
    print("-" * 50)

    if total_failures == 0:
        print("現在、未解決の失敗はありません。✨")
        return

    reason_labels = {
        'no_results': '検索結果なし',
        'gemini_no_info': 'LLM抽出失敗 (gemini_no_info)',
        'missing_brewery_or_name': '醸造所/ビール名不足',
        'final_validation_mismatch': '最終バリデーション不一致',
        'untappd_scrape_error': 'Untappd詳細スクレイプ失敗',
        'missing_info': '情報不足 (Gemini抽出失敗など)',
        'network_error': 'ネットワークエラー/404/406',
        'validation_failed': 'バリデーション失敗 (醸造所名不一致など)',
        'multiple_results': '複数の候補あり',
        'set_product': 'セット商品 (スキップ対象)',
    }

    reason_counts = Counter(item['failure_reason'] for item in rows)
    for reason, count in reason_counts.most_common():
        label = reason_labels.get(reason, reason)
        print(f"- {label:<28}: {count} 件")

    # Last 24h breakdown
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_rows = []
    for item in rows:
        ts = item.get('last_failed_at')
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                if dt >= cutoff_24h:
                    recent_rows.append(item)
            except Exception:
                pass

    print("-" * 50)
    print(f"直近24時間の新規/再失敗: {len(recent_rows)} 件")
    for reason, count in Counter(r['failure_reason'] for r in recent_rows).most_common():
        label = reason_labels.get(reason, reason)
        print(f"  - {label:<26}: {count} 件")

    # Shop (domain) breakdown
    print("-" * 50)
    print("ショップ(ドメイン)別:")
    domain_counts = Counter(urlparse(item['product_url']).netloc for item in rows if item.get('product_url'))
    for domain, count in domain_counts.most_common():
        print(f"  - {domain:<26}: {count} 件")

    # In-Stock beer-only count
    in_stock_missing = (
        supabase.table('beer_info_view')
        .select('url', count='exact', head=True)
        .eq('stock_status', 'In Stock')
        .eq('product_type', 'beer')
        .or_('untappd_url.is.null,untappd_url.ilike.%/search?%')
        .execute()
    )
    print("-" * 50)
    print(f"在庫ありビール単体(product_type=beer)の未紐づけ数: {in_stock_missing.count} 件")


if __name__ == "__main__":
    asyncio.run(main())

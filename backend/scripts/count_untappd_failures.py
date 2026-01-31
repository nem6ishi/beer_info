import asyncio
from backend.src.core.db import get_supabase_client

async def main():
    supabase = get_supabase_client()
    
    # Count unique failed URLs that are not resolved
    response = supabase.table('untappd_search_failures') \
        .select('failure_reason', count='exact') \
        .eq('resolved', False) \
        .execute()
    
    # For more detailed counts by reason
    detailed_response = supabase.table('untappd_search_failures') \
        .select('failure_reason') \
        .eq('resolved', False) \
        .execute()
    
    from collections import Counter
    reasons = [item['failure_reason'] for item in detailed_response.data]
    reason_counts = Counter(reasons)
    
    total_failures = len(reasons)
    
    print(f"📊 Untappd 検索失敗の統計 (未解決のみ)")
    print("=" * 40)
    print(f"合計失敗数: {total_failures} 件")
    print("-" * 40)
    
    if total_failures == 0:
        print("現在、未解決の失敗はありません。✨")
        return

    # Japanese labels for reasons
    reason_labels = {
        'no_results': '検索結果なし',
        'missing_info': '情報不足 (Gemini抽出失敗など)',
        'network_error': 'ネットワークエラー/404/406',
        'validation_failed': 'バリデーション失敗 (醸造所名不一致など)',
        'multiple_results': '複数の候補あり',
        'set_product': 'セット商品 (スキップ対象)'
    }

    for reason, count in reason_counts.most_common():
        label = reason_labels.get(reason, reason)
        print(f"- {label:<20}: {count} 件")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Display and analyze Untappd search failures.
Shows statistics and details of failed searches.
"""
import sys
import argparse
from datetime import datetime
from collections import Counter
from app.core.db import get_supabase_client


def show_statistics(failures):
    """Display summary statistics of failures."""
    print("\n" + "="*70)
    print("📊 FAILURE STATISTICS")
    print("="*70)
    
    total = len(failures)
    print(f"\n総失敗件数: {total}")
    
    if not failures:
        return
    
    # Count by reason
    reasons = Counter(f['failure_reason'] for f in failures)
    print("\n失敗理由別:")
    for reason, count in reasons.most_common():
        pct = (count / total) * 100
        print(f"  • {reason:20s}: {count:4d} ({pct:5.1f}%)")
    
    # Count by attempts
    attempts = Counter(f['search_attempts'] for f in failures)
    print("\n試行回数別:")
    for attempt, count in sorted(attempts.items()):
        pct = (count / total) * 100
        print(f"  • {attempt}回: {count:4d} ({pct:5.1f}%)")
    
    # Recent failures
    recent = sorted(failures, key=lambda x: x['last_failed_at'], reverse=True)[:5]
    print("\n最近の失敗 (5件):")
    for f in recent:
        name = f.get('beer_name') or f.get('beer_name_jp') or 'Unknown'
        brewery = f.get('brewery_name') or 'Unknown'
        reason = f['failure_reason']
        attempts = f['search_attempts']
        print(f"  • [{reason}] {brewery} - {name} (試行{attempts}回)")


def show_details(failures, limit=20):
    """Display detailed failure information."""
    print("\n" + "="*70)
    print(f"📋 FAILURE DETAILS (最新{limit}件)")
    print("="*70)
    
    sorted_failures = sorted(failures, key=lambda x: x['last_failed_at'], reverse=True)[:limit]
    
    for i, f in enumerate(sorted_failures, 1):
        print(f"\n{i}. {'-'*66}")
        
        beer_name = f.get('beer_name') or '未設定'
        beer_name_jp = f.get('beer_name_jp')
        brewery_name = f.get('brewery_name') or '未設定'
        
        print(f"ビール名: {beer_name}")
        if beer_name_jp:
            print(f"  (日本語: {beer_name_jp})")
        print(f"ブルワリー: {brewery_name}")
        print(f"失敗理由: {f['failure_reason']}")
        print(f"試行回数: {f['search_attempts']}回")
        print(f"初回失敗: {f['first_failed_at'][:10]}")
        print(f"最終失敗: {f['last_failed_at'][:10]}")
        
        if f.get('last_error_message'):
            error = f['last_error_message']
            if len(error) > 100:
                error = error[:97] + "..."
            print(f"エラー: {error}")
        
        # Show product URL (truncated)
        url = f.get('product_url', '')
        if len(url) > 70:
            url = url[:67] + "..."
        print(f"URL: {url}")


def main():
    parser = argparse.ArgumentParser(description='Display Untappd search failures')
    parser.add_argument('--reason', help='Filter by failure reason', 
                       choices=['missing_info', 'no_results', 'network_error', 'validation_failed'])
    parser.add_argument('--limit', type=int, default=20, help='Number of details to show (default: 20)')
    parser.add_argument('--resolved', action='store_true', help='Show resolved failures instead of unresolved')
    parser.add_argument('--stats-only', action='store_true', help='Show only statistics, not details')
    
    args = parser.parse_args()
    
    supabase = get_supabase_client()
    
    # Build query
    query = supabase.table('untappd_search_failures').select('*')
    
    if args.resolved:
        query = query.eq('resolved', True)
    else:
        query = query.eq('resolved', False)
    
    if args.reason:
        query = query.eq('failure_reason', args.reason)
    
    # Execute query
    response = query.order('last_failed_at', desc=True).execute()
    failures = response.data
    
    if not failures:
        print("\n✨ 失敗ケースはありません！")
        return 0
    
    # Show statistics
    show_statistics(failures)
    
    # Show details unless stats-only
    if not args.stats_only:
        show_details(failures, args.limit)
    
    print("\n" + "="*70)
    print(f"💡 ヒント: 特定の理由でフィルタするには --reason オプションを使用")
    print(f"   例: python {sys.argv[0]} --reason no_results")
    print("="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

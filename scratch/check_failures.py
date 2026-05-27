# scratch/check_failures.py
import sys
import os

# プロジェクトのルートディレクトリを Python パスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.core.db import get_supabase_client

def main():
    print("Connecting to Supabase...")
    supabase = get_supabase_client()
    
    # 最近の未解決の失敗レコードを取得
    print("Fetching active untappd search failures...")
    try:
        response = (
            supabase.table("untappd_search_failures")
            .select("id, brewery_name, beer_name, beer_name_jp, failure_reason, last_error_message, last_failed_at, resolved, product_url")
            .eq("resolved", False)
            .order("last_failed_at", desc=True)
            .limit(100)
            .execute()
        )
        
        failures = response.data
        if not failures:
            print("未解決の失敗レコードはありませんでした。")
            return
            
        print(f"見つかった未解決の失敗レコード: {len(failures)} 件")
        
        # 結果をテキストファイルに書き出す
        output_path = os.path.join(os.path.dirname(__file__), "failures_report.txt")
        with open(output_path, "w", encoding="utf-8") as f_out:
            f_out.write(f"未解決のUntappd enrich失敗レコード (最新{len(failures)}件)\n")
            f_out.write("=" * 80 + "\n")
            for i, f in enumerate(failures, 1):
                f_out.write(f"[{i}] 日時: {f.get('last_failed_at')} | 理由: {f.get('failure_reason')}\n")
                f_out.write(f"  ブルワリー: {f.get('brewery_name')}\n")
                f_out.write(f"  ビール名(EN): {f.get('beer_name')}\n")
                f_out.write(f"  ビール名(JP): {f.get('beer_name_jp')}\n")
                f_out.write(f"  URL: {f.get('product_url')}\n")
                if f.get('last_error_message'):
                    f_out.write(f"  エラー詳細: {f.get('last_error_message')}\n")
                f_out.write("-" * 80 + "\n")
        
        print(f"結果を {output_path} に書き出しました。")
            
    except Exception as e:
        print(f"Error querying table: {e}")

if __name__ == "__main__":
    main()

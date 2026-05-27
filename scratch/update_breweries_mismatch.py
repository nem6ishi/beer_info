# scratch/update_breweries_mismatch.py
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.core.db import get_supabase_client

def main():
    supabase = get_supabase_client()
    print("Supabase接続完了。マスタデータの更新を開始します。")

    # 1. Derailleur Brew Works の更新
    print("\n--- 1. Derailleur Brew Works の更新 ---")
    try:
        res = supabase.table("breweries").select("*").eq("name_en", "Derailleur Brew Works").execute()
        if res.data:
            brewery = res.data[0]
            brewery_id = brewery["id"]
            print(f"既存の Derailleur Brew Works を発見 (ID: {brewery_id})")
            
            update_payload = {
                "name_jp": "ディレイラーブリューワークス",
                "aliases": ["ディレイラーブリューワークス", "ディレイラー", "ディレイラ"]
            }
            
            update_res = supabase.table("breweries").update(update_payload).eq("id", brewery_id).execute()
            if update_res.data:
                print("  => 成功: 日本語名とエイリアスを更新しました。")
            else:
                print("  => エラー: 更新データが返されませんでした。")
        else:
            print("Derailleur Brew Works が見つからないため、新規作成します。")
            insert_payload = {
                "name_en": "Derailleur Brew Works",
                "name_jp": "ディレイラーブリューワークス",
                "aliases": ["ディレイラーブリューワークス", "ディレイラー", "ディレイラ"],
                "untappd_url": "https://untappd.com/DerailleurBrewWorks"
            }
            insert_res = supabase.table("breweries").insert(insert_payload).execute()
            if insert_res.data:
                print("  => 成功: 新規追加しました。")
            else:
                print("  => エラー: 追加失敗。")
    except Exception as e:
        print(f"  ❌ エラー: {e}")

    # 2. Son of a Smith (サノバスミス) の追加/更新
    print("\n--- 2. Son of a Smith の更新/追加 ---")
    try:
        res = supabase.table("breweries").select("*").eq("name_en", "Son of a Smith").execute()
        if res.data:
            brewery = res.data[0]
            brewery_id = brewery["id"]
            print(f"既存の Son of a Smith を発見 (ID: {brewery_id})")
            
            update_payload = {
                "name_jp": "サノバスミス",
                "aliases": ["サノバスミス", "Sano-ba Smith", "Sanoba Smith"]
            }
            
            update_res = supabase.table("breweries").update(update_payload).eq("id", brewery_id).execute()
            if update_res.data:
                print("  => 成功: 日本語名とエイリアスを更新しました。")
            else:
                print("  => エラー: 更新データが返されませんでした。")
        else:
            print("Son of a Smith が見つからないため、新規作成します。")
            insert_payload = {
                "name_en": "Son of a Smith",
                "name_jp": "サノバスミス",
                "aliases": ["サノバスミス", "Sano-ba Smith", "Sanoba Smith"],
                "untappd_url": "https://untappd.com/w/son-of-a-smith-hard-cider/333798"
            }
            insert_res = supabase.table("breweries").insert(insert_payload).execute()
            if insert_res.data:
                print("  => 成功: 新規追加しました。")
            else:
                print("  => エラー: 追加失敗。")
    except Exception as e:
        print(f"  ❌ エラー: {e}")

    print("\nマスタデータの更新処理が完了しました。")

if __name__ == "__main__":
    main()

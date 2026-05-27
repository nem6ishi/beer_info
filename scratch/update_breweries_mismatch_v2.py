# scratch/update_breweries_mismatch_v2.py
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.core.db import get_supabase_client

def main():
    supabase = get_supabase_client()
    print("Supabase接続完了。マスタデータ（第2弾）の更新を開始します。")

    updates = [
        {
            "target_en": "VERTERE",
            "payload": {
                "name_jp": "バテレ",
                "aliases": ["バテレ", "バテラ"]
            }
        },
        {
            "target_en": "Two Rabbits Brewing Company",
            "payload": {
                "name_jp": "二兎醸造",
                "aliases": ["二兎醸造", "二兎", "Two Rabbits"]
            }
        },
        {
            "target_en": "Oriental Brewing",
            "payload": {
                "name_jp": "オリエンタルブルーイング",
                "aliases": ["オリエンタルブルーイング", "オリエンタル"]
            }
        },
        {
            "target_en": "Tono Brewing",
            "payload": {
                "name_jp": "遠野醸造",
                "aliases": ["遠野醸造", "遠野麦酒"]
            }
        },
        {
            "target_en": "Hiruzen Brewing",
            "payload": {
                "name_jp": "蒜山高原ビール",
                "aliases": ["蒜山ビール", "蒜山高原ビール", "蒜山"]
            }
        }
    ]

    # 1. 既存ブルワリーの更新
    for item in updates:
        target = item["target_en"]
        payload = item["payload"]
        print(f"\n--- {target} の更新 ---")
        try:
            res = supabase.table("breweries").select("*").eq("name_en", target).execute()
            if res.data:
                brewery = res.data[0]
                brewery_id = brewery["id"]
                print(f"既存のレコードを発見 (ID: {brewery_id})")
                update_res = supabase.table("breweries").update(payload).eq("id", brewery_id).execute()
                if update_res.data:
                    print(f"  => 成功: name_jp={payload['name_jp']}, aliases={payload['aliases']} に更新しました。")
                else:
                    print("  => エラー: 更新データが返されませんでした。")
            else:
                print(f"  ⚠️ 警告: {target} のレコードが見つかりません。")
        except Exception as e:
            print(f"  ❌ エラー: {e}")

    # 2. Falò Brewing (ファロブルーイング) の追加/更新
    print("\n--- Falò Brewing の追加/更新 ---")
    try:
        res = supabase.table("breweries").select("*").eq("name_en", "Falò Brewing").execute()
        if res.data:
            brewery = res.data[0]
            brewery_id = brewery["id"]
            print(f"既存の Falò Brewing を発見 (ID: {brewery_id})")
            update_payload = {
                "name_jp": "ファロブルーイング",
                "aliases": ["ファロブルーイング", "ファロ", "Falo Brewing", "Falò Brewing"]
            }
            update_res = supabase.table("breweries").update(update_payload).eq("id", brewery_id).execute()
            if update_res.data:
                print("  => 成功: 日本語名とエイリアスを更新しました。")
            else:
                print("  => エラー: 更新データが返されませんでした。")
        else:
            print("Falò Brewing が見つからないため、新規作成します。")
            insert_payload = {
                "name_en": "Falò Brewing",
                "name_jp": "ファロブルーイング",
                "aliases": ["ファロブルーイング", "ファロ", "Falo Brewing", "Falò Brewing"],
                "untappd_url": "https://untappd.com/w/falo-brewing/545081"
            }
            insert_res = supabase.table("breweries").insert(insert_payload).execute()
            if insert_res.data:
                print("  => 成功: 新規追加しました。")
            else:
                print("  => エラー: 追加失敗。")
    except Exception as e:
        print(f"  ❌ エラー: {e}")

    # 3. Son of a Smith (サノバスミス) の追加/更新 (正式名 'Son of a Smith Hard Cider' へ更新)
    print("\n--- Son of a Smith Hard Cider の更新/追加 ---")
    try:
        # 古い誤った 'Son of a Smith' レコードがあれば一度削除
        res_old = supabase.table("breweries").select("*").eq("name_en", "Son of a Smith").execute()
        if res_old.data:
            print(f"  => 古い 'Son of a Smith' レコードを発見 (ID: {res_old.data[0]['id']})。削除します。")
            supabase.table("breweries").delete().eq("id", res_old.data[0]["id"]).execute()

        res = supabase.table("breweries").select("*").eq("name_en", "Son of a Smith Hard Cider").execute()
        if res.data:
            brewery = res.data[0]
            brewery_id = brewery["id"]
            print(f"既存の Son of a Smith Hard Cider を発見 (ID: {brewery_id})")
            
            update_payload = {
                "name_jp": "サノバスミス",
                "aliases": ["サノバスミス", "Sano-ba Smith", "Sanoba Smith", "Son of a Smith"]
            }
            
            update_res = supabase.table("breweries").update(update_payload).eq("id", brewery_id).execute()
            if update_res.data:
                print("  => 成功: 日本語名とエイリアスを更新しました。")
            else:
                print("  => エラー: 更新データが返されませんでした。")
        else:
            print("Son of a Smith Hard Cider が見つからないため、新規作成します。")
            insert_payload = {
                "name_en": "Son of a Smith Hard Cider",
                "name_jp": "サノバスミス",
                "aliases": ["サノバスミス", "Sano-ba Smith", "Sanoba Smith", "Son of a Smith"],
                "untappd_url": "https://untappd.com/w/son-of-a-smith-hard-cider/333798"
            }
            insert_res = supabase.table("breweries").insert(insert_payload).execute()
            if insert_res.data:
                print("  => 成功: 新規追加しました。")
            else:
                print("  => エラー: 追加失敗。")
    except Exception as e:
        print(f"  ❌ エラー: {e}")

    print("\nマスタデータ（第2弾）の更新処理が完了しました。")

if __name__ == "__main__":
    main()

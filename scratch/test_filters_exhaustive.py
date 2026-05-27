import httpx
import sys

BASE_URL = "http://localhost:3000"

def check_server():
    """ローカルサーバーの起動確認"""
    try:
        response = httpx.get(f"{BASE_URL}/api/beers?limit=5", timeout=5.0)
        if response.status_code == 200:
            print("🟢 ローカル開発サーバーが起動しています。テストを実行します。\n")
            return True
        else:
            print(f"🔴 エラー: ローカル開発サーバーは起動していますが、API (/api/beers) がステータスコード {response.status_code} を返しました。")
            print("   サーバーログを確認してください。")
            return False
    except Exception as e:
        print("🔴 エラー: ローカル開発サーバー (http://localhost:3000) が起動していないか、接続できません。")
        print("   テストを実行する前に、別のターミナルで以下のコマンドを実行してサーバーを起動してください：")
        print("   npm run dev")
        print(f"   詳細エラー: {e}")
        return False

def print_result(test_name, passed, message=""):
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"  {status} | {test_name}")
    if message:
        print(f"    └ {message}")

def test_beers_api():
    """Individual View API (/api/beers) のフィルターテスト"""
    print("=== [1] Individual View API (/api/beers) のテスト ===")
    
    # 1. 初期データ取得してサンプリング用の値を手に入れる
    try:
        res = httpx.get(f"{BASE_URL}/api/beers?limit=100")
        if res.status_code != 200:
            print(f"🔴 初期データ取得失敗: ステータスコード {res.status_code}")
            return False
        data = res.json()
        beers = data.get("beers", [])
        if not beers:
            print("⚠️ 警告: データベースが空か、ビールが取得できませんでした。")
            return False
    except Exception as e:
        print(f"🔴 初期データ取得中に例外が発生しました: {e}")
        return False

    # サンプリング
    sample_shop = None
    sample_style = None
    sample_brewery = None
    sample_product_type = None
    sample_abv = None
    sample_ibu = None
    sample_rating = None
    
    for b in beers:
        if not sample_shop and b.get("shop"):
            sample_shop = b["shop"]
        if not sample_style and b.get("untappd_style"):
            sample_style = b["untappd_style"]
        if not sample_brewery and b.get("untappd_brewery_name"):
            sample_brewery = b["untappd_brewery_name"]
        if not sample_product_type and b.get("product_type"):
            sample_product_type = b["product_type"]
        if sample_abv is None and b.get("untappd_abv") is not None:
            sample_abv = b["untappd_abv"]
        if sample_ibu is None and b.get("untappd_ibu") is not None:
            sample_ibu = b["untappd_ibu"]
        if sample_rating is None and b.get("untappd_rating") is not None:
            sample_rating = b["untappd_rating"]

    print(f"サンプリングされたデータ:")
    print(f"  Shop: {sample_shop}")
    print(f"  Style: {sample_style}")
    print(f"  Brewery: {sample_brewery}")
    print(f"  Product Type: {sample_product_type}")
    print(f"  ABV: {sample_abv}")
    print(f"  IBU: {sample_ibu}")
    print(f"  Rating: {sample_rating}\n")

    all_passed = True

    # --- Test Case 1: Store (店舗) ---
    if sample_shop:
        params = {"shop": sample_shop, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                if item.get("shop") != sample_shop:
                    passed = False
                    msg = f"指定した店舗 '{sample_shop}' 以外のビールが含まれています: {item.get('shop')}"
                    break
        print_result("Store フィルター (単一店舗)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 2: ABV (アルコール度数) ---
    if sample_abv is not None:
        min_abv = max(0.0, sample_abv - 1.0)
        max_abv = sample_abv + 1.0
        params = {"min_abv": min_abv, "max_abv": max_abv, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                abv = item.get("untappd_abv")
                if abv is None:
                    passed = False
                    msg = "ABVがnullのデータが含まれています"
                    break
                if not (min_abv <= abv <= max_abv):
                    passed = False
                    msg = f"ABV範囲外のビールが含まれています: {abv} (範囲: {min_abv}〜{max_abv})"
                    break
        print_result("ABV フィルター (範囲指定)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 3: IBU (苦味指標) ---
    if sample_ibu is not None:
        min_ibu = max(0, int(sample_ibu) - 10)
        max_ibu = int(sample_ibu) + 10
        params = {"min_ibu": min_ibu, "max_ibu": max_ibu, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                ibu = item.get("untappd_ibu")
                if ibu is None:
                    passed = False
                    msg = "IBUがnullのデータが含まれています"
                    break
                if not (min_ibu <= ibu <= max_ibu):
                    passed = False
                    msg = f"IBU範囲外のビールが含まれています: {ibu} (範囲: {min_ibu}〜{max_ibu})"
                    break
        print_result("IBU フィルター (範囲指定)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 4: Rating (評価) ---
    if sample_rating is not None:
        min_rating = max(0.0, sample_rating - 0.5)
        params = {"min_rating": min_rating, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                rating = item.get("untappd_rating")
                if rating is None:
                    passed = False
                    msg = "Ratingがnullのデータが含まれています"
                    break
                if rating < min_rating:
                    passed = False
                    msg = f"指定Rating未満のビールが含まれています: {rating} (最小: {min_rating})"
                    break
        print_result("Rating フィルター (最小値)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 5: Style (スタイル) ---
    if sample_style:
        params = {"style_filter": sample_style, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                if item.get("untappd_style") != sample_style:
                    passed = False
                    msg = f"指定スタイル '{sample_style}' 以外のビールが含まれています: {item.get('untappd_style')}"
                    break
        print_result("Style フィルター (単一スタイル)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 6: Brewery (ブルワリー) ---
    if sample_brewery:
        params = {"brewery_filter": sample_brewery, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                if item.get("untappd_brewery_name") != sample_brewery:
                    passed = False
                    msg = f"指定ブルワリー '{sample_brewery}' 以外のビールが含まれています: {item.get('untappd_brewery_name')}"
                    break
        print_result("Brewery フィルター (単一ブルワリー)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 7: Stock (在庫) ---
    # in_stock
    params_in = {"stock_filter": "in_stock", "limit": 50}
    res_in = httpx.get(f"{BASE_URL}/api/beers", params=params_in)
    passed_in = True
    msg_in = ""
    if res_in.status_code != 200:
        passed_in = False
        msg_in = f"ステータスコードエラー: {res_in.status_code}"
    else:
        items = res_in.json().get("beers", [])
        for item in items:
            if item.get("stock_status") != "In Stock":
                passed_in = False
                msg_in = f"In Stock フィルターに 'Sold Out' のビールが含まれています: {item.get('name')}"
                break
    print_result("Stock フィルター (In Stockのみ)", passed_in, msg_in)
    if not passed_in: all_passed = False

    # sold_out
    params_out = {"stock_filter": "sold_out", "limit": 50}
    res_out = httpx.get(f"{BASE_URL}/api/beers", params=params_out)
    passed_out = True
    msg_out = ""
    if res_out.status_code != 200:
        passed_out = False
        msg_out = f"ステータスコードエラー: {res_out.status_code}"
    else:
        items = res_out.json().get("beers", [])
        for item in items:
            if item.get("stock_status") != "In Stock":
                # OK
                pass
            else:
                passed_out = False
                msg_out = f"Sold Out フィルターに 'In Stock' のビールが含まれています: {item.get('name')}"
                break
    print_result("Stock フィルター (Sold Outのみ)", passed_out, msg_out)
    if not passed_out: all_passed = False

    # --- Test Case 8: Product Type (種類) ---
    if sample_product_type:
        params = {"product_type": sample_product_type, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            items = res.json().get("beers", [])
            for item in items:
                if item.get("product_type") != sample_product_type:
                    passed = False
                    msg = f"指定種別 '{sample_product_type}' 以外のビールが含まれています: {item.get('product_type')}"
                    break
        print_result("Product Type フィルター", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 9: Untappd Status (紐付状況) ---
    # linked
    params_linked = {"untappd_status": "linked", "limit": 50}
    res_linked = httpx.get(f"{BASE_URL}/api/beers", params=params_linked)
    passed_linked = True
    msg_linked = ""
    if res_linked.status_code != 200:
        passed_linked = False
        msg_linked = f"ステータスコードエラー: {res_linked.status_code}"
    else:
        items = res_linked.json().get("beers", [])
        for item in items:
            url = item.get("untappd_url")
            if not url or "/search?" in url:
                passed_linked = False
                msg_linked = f"linked フィルターに紐付データがない、または検索中のビールが含まれています: {item.get('name')} (URL: {url})"
                break
    print_result("Untappd Status フィルター (linked)", passed_linked, msg_linked)
    if not passed_linked: all_passed = False

    # missing
    params_missing = {"untappd_status": "missing", "limit": 50}
    res_missing = httpx.get(f"{BASE_URL}/api/beers", params=params_missing)
    passed_missing = True
    msg_missing = ""
    if res_missing.status_code != 200:
        passed_missing = False
        msg_missing = f"ステータスコードエラー: {res_missing.status_code}"
    else:
        items = res_missing.json().get("beers", [])
        for item in items:
            url = item.get("untappd_url")
            p_type = item.get("product_type")
            is_valid_missing = (not url or "/search?" in url) and (p_type is None or p_type == "beer")
            if not is_valid_missing:
                passed_missing = False
                msg_missing = f"missing フィルターに紐付済、またはビール以外のデータが含まれています: {item.get('name')} (URL: {url}, Type: {p_type})"
                break
    print_result("Untappd Status フィルター (missing)", passed_missing, msg_missing)
    if not passed_missing: all_passed = False

    # --- Test Case 10: 複合フィルター ---
    if sample_shop and sample_abv is not None:
        min_abv = max(0.0, sample_abv - 2.0)
        max_abv = sample_abv + 2.0
        params = {
            "shop": sample_shop,
            "min_abv": min_abv,
            "max_abv": max_abv,
            "stock_filter": "in_stock",
            "limit": 50
        }
        res = httpx.get(f"{BASE_URL}/api/beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
            if res.status_code == 500:
                msg += " (⚠️ データベース結合キーのインデックス idx_scraped_beers_untappd_url / idx_untappd_data_brewery_url が未適用のためのタイムアウトである可能性が高いです。009_optimize_performance_and_fix_jsonb.sql を実行してください)"
        else:
            items = res.json().get("beers", [])
            for item in items:
                abv = item.get("untappd_abv")
                if item.get("shop") != sample_shop:
                    passed = False
                    msg = f"複合フィルターで店舗が不一致: {item.get('shop')}"
                    break
                if abv is None or not (min_abv <= abv <= max_abv):
                    passed = False
                    msg = f"複合フィルターでABV範囲外: {abv}"
                    break
                if item.get("stock_status") != "In Stock":
                    passed = False
                    msg = f"複合フィルターで在庫ステータスがIn Stockではない: {item.get('stock_status')}"
                    break
        print_result("複合フィルター (Store + ABV範囲 + In Stock)", passed, msg)
        if not passed: all_passed = False

    print()
    return all_passed

def test_grouped_beers_api():
    """Grouped View API (/api/grouped-beers) のフィルターテスト"""
    print("=== [2] Grouped View API (/api/grouped-beers) のテスト ===")
    
    # 1. 初期データ取得
    try:
        res = httpx.get(f"{BASE_URL}/api/grouped-beers?limit=100")
        if res.status_code != 200:
            print(f"🔴 初期データ取得失敗: ステータスコード {res.status_code}")
            return False
        data = res.json()
        groups = data.get("groups", [])
        if not groups:
            print("⚠️ 警告: データベースが空か、グループビールが取得できませんでした。")
            return False
    except Exception as e:
        print(f"🔴 初期データ取得中に例外が発生しました: {e}")
        return False

    # サンプリング
    sample_shop = None
    sample_style = None
    sample_brewery = None
    sample_product_type = None
    sample_abv = None
    sample_ibu = None
    sample_rating = None

    for g in groups:
        items = g.get("items", [])
        if not sample_shop and items:
            for item in items:
                if item.get("shop"):
                    sample_shop = item["shop"]
                    break
        if not sample_style and g.get("style"):
            sample_style = g["style"]
        if not sample_brewery and g.get("brewery_name"):
            sample_brewery = g["brewery_name"]
        if not sample_product_type and g.get("product_type"):
            sample_product_type = g["product_type"]
        if sample_abv is None and g.get("abv") is not None:
            sample_abv = g["abv"]
        if sample_ibu is None and g.get("ibu") is not None:
            sample_ibu = g["ibu"]
        if sample_rating is None and g.get("rating") is not None:
            sample_rating = g["rating"]

    print(f"サンプリングされたデータ (グループ表示用):")
    print(f"  Shop: {sample_shop}")
    print(f"  Style: {sample_style}")
    print(f"  Brewery: {sample_brewery}")
    print(f"  Product Type: {sample_product_type}")
    print(f"  ABV: {sample_abv}")
    print(f"  IBU: {sample_ibu}")
    print(f"  Rating: {sample_rating}\n")

    all_passed = True

    # --- Test Case 1: Store (店舗) ---
    if sample_shop:
        params = {"shop": sample_shop, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                items = g.get("items", [])
                has_shop = any(item.get("shop") == sample_shop for item in items)
                if not has_shop:
                    passed = False
                    msg = f"グループ内に指定した店舗 '{sample_shop}' のアイテムが含まれていません: {g.get('beer_name')}"
                    break
        print_result("Store フィルター (単一店舗)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 2: ABV (アルコール度数) ---
    if sample_abv is not None:
        min_abv = max(0.0, sample_abv - 1.0)
        max_abv = sample_abv + 1.0
        params = {"min_abv": min_abv, "max_abv": max_abv, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                abv = g.get("abv")
                if abv is None:
                    passed = False
                    msg = "ABVがnullのデータが含まれています"
                    break
                if not (min_abv <= abv <= max_abv):
                    passed = False
                    msg = f"ABV範囲外のグループが含まれています: {abv} (範囲: {min_abv}〜{max_abv})"
                    break
        print_result("ABV フィルター (範囲指定)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 3: IBU (苦味指標) ---
    if sample_ibu is not None:
        min_ibu = max(0, int(sample_ibu) - 10)
        max_ibu = int(sample_ibu) + 10
        params = {"min_ibu": min_ibu, "max_ibu": max_ibu, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                ibu = g.get("ibu")
                if ibu is None:
                    passed = False
                    msg = "IBUがnullのデータが含まれています"
                    break
                if not (min_ibu <= ibu <= max_ibu):
                    passed = False
                    msg = f"IBU範囲外のグループが含まれています: {ibu} (範囲: {min_ibu}〜{max_ibu})"
                    break
        print_result("IBU フィルター (範囲指定)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 4: Rating (評価) ---
    if sample_rating is not None:
        min_rating = max(0.0, sample_rating - 0.5)
        params = {"min_rating": min_rating, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                rating = g.get("rating")
                if rating is None:
                    passed = False
                    msg = "Ratingがnullのデータが含まれています"
                    break
                if rating < min_rating:
                    passed = False
                    msg = f"指定Rating未満のグループが含まれています: {rating} (最小: {min_rating})"
                    break
        print_result("Rating フィルター (最小値)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 5: Style (スタイル) ---
    if sample_style:
        params = {"style_filter": sample_style, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                if g.get("style") != sample_style:
                    passed = False
                    msg = f"指定スタイル '{sample_style}' 以外のグループが含まれています: {g.get('style')}"
                    break
        print_result("Style フィルター (単一スタイル)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 6: Brewery (ブルワリー) ---
    if sample_brewery:
        params = {"brewery_filter": sample_brewery, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                if g.get("brewery_name") != sample_brewery:
                    passed = False
                    msg = f"指定ブルワリー '{sample_brewery}' 以外のグループが含まれています: {g.get('brewery_name')}"
                    break
        print_result("Brewery フィルター (単一ブルワリー)", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 7: Stock (在庫) ---
    # in_stock
    params_in = {"stock_filter": "in_stock", "limit": 50}
    res_in = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params_in)
    passed_in = True
    msg_in = ""
    if res_in.status_code != 200:
        passed_in = False
        msg_in = f"ステータスコードエラー: {res_in.status_code}"
    else:
        groups_res = res_in.json().get("groups", [])
        for g in groups_res:
            items = g.get("items", [])
            has_in_stock = any(item.get("stock_status") == "In Stock" for item in items)
            if not has_in_stock:
                passed_in = False
                msg_in = f"In Stock フィルターに 'In Stock' なしグループが含まれています: {g.get('beer_name')}"
                break
    print_result("Stock フィルター (In Stockのみ)", passed_in, msg_in)
    if not passed_in: all_passed = False

    # sold_out
    params_out = {"stock_filter": "sold_out", "limit": 50}
    res_out = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params_out)
    passed_out = True
    msg_out = ""
    if res_out.status_code != 200:
        passed_out = False
        msg_out = f"ステータスコードエラー: {res_out.status_code}"
    else:
        groups_res = res_out.json().get("groups", [])
        for g in groups_res:
            items = g.get("items", [])
            has_in_stock = any(item.get("stock_status") == "In Stock" for item in items)
            if has_in_stock:
                passed_out = False
                msg_out = f"Sold Out フィルターに 'In Stock' ありグループが含まれています: {g.get('beer_name')}"
                break
    print_result("Stock フィルター (Sold Outのみ)", passed_out, msg_out)
    if not passed_out: all_passed = False

    # --- Test Case 8: Product Type (種類) ---
    if sample_product_type:
        params = {"product_type": sample_product_type, "limit": 50}
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                if g.get("product_type") != sample_product_type:
                    passed = False
                    msg = f"指定種別 '{sample_product_type}' 以外のグループが含まれています: {g.get('product_type')}"
                    break
        print_result("Product Type フィルター", passed, msg)
        if not passed: all_passed = False

    # --- Test Case 9: 複合フィルター ---
    if sample_shop and sample_abv is not None:
        min_abv = max(0.0, sample_abv - 2.0)
        max_abv = sample_abv + 2.0
        params = {
            "shop": sample_shop,
            "min_abv": min_abv,
            "max_abv": max_abv,
            "stock_filter": "in_stock",
            "limit": 50
        }
        res = httpx.get(f"{BASE_URL}/api/grouped-beers", params=params)
        passed = True
        msg = ""
        if res.status_code != 200:
            passed = False
            msg = f"ステータスコードエラー: {res.status_code}"
        else:
            groups_res = res.json().get("groups", [])
            for g in groups_res:
                abv = g.get("abv")
                items = g.get("items", [])
                valid_item_found = any(
                    item.get("shop") == sample_shop and item.get("stock_status") == "In Stock"
                    for item in items
                )
                if not valid_item_found:
                    passed = False
                    msg = f"複合フィルターで指定店舗のIn Stockアイテムが見つかりません: {g.get('beer_name')}"
                    break
                if abv is None or not (min_abv <= abv <= max_abv):
                    passed = False
                    msg = f"複合フィルターでABV範囲外: {abv}"
                    break
        print_result("複合フィルター (Store + ABV範囲 + In Stock)", passed, msg)
        if not passed: all_passed = False

    print()
    return all_passed

def main():
    if not check_server():
        sys.exit(1)
        
    beers_passed = test_beers_api()
    grouped_passed = test_grouped_beers_api()
    
    # タイムアウト等を含む全体判定
    if beers_passed and grouped_passed:
        print("🎉 ALL TESTS PASSED! すべてのフィルター項目が正常に動作しています。")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED! 一部のフィルターで期待しない挙動がありました。")
        sys.exit(1)

if __name__ == "__main__":
    main()

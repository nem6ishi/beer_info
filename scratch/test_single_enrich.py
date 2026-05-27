import sys
import os
import asyncio
import logging

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s"
)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.src.services.store.brewery_manager import BreweryManager
from backend.src.services.gemini.extractor import GeminiExtractor
from backend.src.services.untappd.searcher import get_untappd_url

async def test_verification():
    print("=== 1. BreweryManager の検知テスト ===")
    bm = BreweryManager()
    
    # テストデータ1: ディレイラーブリューワークス
    test_title_1 = "【ぼくカルダえもん/ディレイラーブリューワークス】"
    matches_1 = bm.find_breweries_in_text(test_title_1)
    print(f"入力タイトル: '{test_title_1}'")
    if matches_1:
        for m in matches_1:
            print(f"  => 検知されたブルワリー: {m.get('name_en')} ({m.get('name_jp')})")
    else:
        print("  => ❌ ブルワリーが検知されませんでした。")

    # テストデータ2: サノバスミス
    test_title_2 = "【SATOYAMA RESEARCH/サノバスミス】"
    matches_2 = bm.find_breweries_in_text(test_title_2)
    print(f"\n入力タイトル: '{test_title_2}'")
    if matches_2:
        for m in matches_2:
            print(f"  => 検知されたブルワリー: {m.get('name_en')} ({m.get('name_jp')})")
    else:
        print("  => ❌ ブルワリーが検知されませんでした。")

    # テストデータ3: バテレ (VERTERE)
    test_title_3 = "くまモンのピルスナー / バテレ"
    matches_3 = bm.find_breweries_in_text(test_title_3)
    print(f"\n入力タイトル: '{test_title_3}'")
    if matches_3:
        for m in matches_3:
            print(f"  => 検知されたブルワリー: {m.get('name_en')} ({m.get('name_jp')})")
    else:
        print("  => ❌ ブルワリーが検知されませんでした。")

    # テストデータ4: ファロブルーイング (Falò Brewing)
    test_title_4 = "Falò IPA / ファロブルーイング"
    matches_4 = bm.find_breweries_in_text(test_title_4)
    print(f"\n入力タイトル: '{test_title_4}'")
    if matches_4:
        for m in matches_4:
            print(f"  => 検知されたブルワリー: {m.get('name_en')} ({m.get('name_jp')})")
    else:
        print("  => ❌ ブルワリーが検知されませんでした。")

    print("\n=== 2. GeminiExtractor による AI 抽出テスト ===")
    extractor = GeminiExtractor()
    if not extractor.client:
        print("  => ❌ Gemini APIクライアントが初期化されていません。")
        return

    # ディレイラー
    known_1 = ", ".join([b['name_en'] for b in matches_1]) if matches_1 else None
    print(f"\nディレイラーの抽出を実行中 (ヒント: {known_1})...")
    res_1 = await extractor.extract_info(test_title_1, known_brewery=known_1, shop="ちょうせいや")
    print(f"  => 抽出結果: Brewery={res_1.get('brewery_name_en')} | Beer={res_1.get('beer_name_en')}")

    # サノバスミス
    known_2 = ", ".join([b['name_en'] for b in matches_2]) if matches_2 else None
    print(f"\nサノバスミスの抽出を実行中 (ヒント: {known_2})...")
    res_2 = await extractor.extract_info(test_title_2, known_brewery=known_2, shop="ちょうせいや")
    print(f"  => 抽出結果: Brewery={res_2.get('brewery_name_en')} | Beer={res_2.get('beer_name_en')}")

    # バテレ
    known_3 = ", ".join([b['name_en'] for b in matches_3]) if matches_3 else None
    print(f"\nバテレの抽出を実行中 (ヒント: {known_3})...")
    res_3 = await extractor.extract_info(test_title_3, known_brewery=known_3, shop="beervolta")
    print(f"  => 抽出結果: Brewery={res_3.get('brewery_name_en')} | Beer={res_3.get('beer_name_en')}")

    # ファロ
    known_4 = ", ".join([b['name_en'] for b in matches_4]) if matches_4 else None
    print(f"\nファロの抽出を実行中 (ヒント: {known_4})...")
    res_4 = await extractor.extract_info(test_title_4, known_brewery=known_4, shop="beervolta")
    print(f"  => 抽出結果: Brewery={res_4.get('brewery_name_en')} | Beer={res_4.get('beer_name_en')}")

    print("\n=== 3. Untappd 検索テスト ===")
    
    # 3-1. ぼくカルダえもん の検索テスト
    brewery_1 = res_1.get("brewery_name_en")
    beer_1 = res_1.get("beer_name_en")
    print(f"\nUntappdで '{brewery_1} - {beer_1}' を検索中...")
    search_res_1 = get_untappd_url(brewery_name=brewery_1, beer_name=beer_1, search_hint=res_1.get("search_hint"), beer_name_core=res_1.get("beer_name_core"))
    print(f"  => 検索結果: Success={search_res_1.get('success')} | URL={search_res_1.get('url')}")

    # 3-2. SATOYAMA RESEARCH の検索テスト
    brewery_2 = res_2.get("brewery_name_en")
    beer_2 = res_2.get("beer_name_en")
    print(f"\nUntappdで '{brewery_2} - {beer_2}' を検索中...")
    search_res_2 = get_untappd_url(brewery_name=brewery_2, beer_name=beer_2, search_hint=res_2.get("search_hint"), beer_name_core=res_2.get("beer_name_core"))
    print(f"  => 検索結果: Success={search_res_2.get('success')} | URL={search_res_2.get('url')}")

    # 3-3. くまモンのピルスナー (VERTERE)
    brewery_3 = res_3.get("brewery_name_en")
    beer_3 = res_3.get("beer_name_en")
    print(f"\nUntappdで '{brewery_3} - {beer_3}' を検索中...")
    search_res_3 = get_untappd_url(brewery_name=brewery_3, beer_name=beer_3, search_hint=res_3.get("search_hint"), beer_name_core=res_3.get("beer_name_core"))
    print(f"  => 検索結果: Success={search_res_3.get('success')} | URL={search_res_3.get('url')}")

    # 3-4. Falò IPA (Falò Brewing)
    brewery_4 = res_4.get("brewery_name_en")
    beer_4 = res_4.get("beer_name_en")
    print(f"\nUntappdで '{brewery_4} - {beer_4}' を検索中...")
    search_res_4 = get_untappd_url(brewery_name=brewery_4, beer_name=beer_4, search_hint=res_4.get("search_hint"), beer_name_core=res_4.get("beer_name_core"))
    print(f"  => 検索結果: Success={search_res_4.get('success')} | URL={search_res_4.get('url')}")

if __name__ == "__main__":
    asyncio.run(test_verification())

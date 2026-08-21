import pytest
from backend.src.services.llm.prompt_builder import PromptBuilder

def test_clean_product_title():
    pb = PromptBuilder()
    
    # 1. Shipping dates and shipping methods
    t1 = "Revision There Are No Good Endings (473ml) / ゼア アー ノー グッド エンディングズ【7/2出荷】"
    cleaned1 = pb.clean_product_title(t1)
    assert "【7/2出荷】" not in cleaned1
    assert cleaned1 == "Revision There Are No Good Endings (473ml) / ゼア アー ノー グッド エンディングズ"
    
    # 2. (空輸) and (空輸便)
    t2 = "(空輸) ロアーブルーイング / エターナル・プランクスター (Hazy Double IPA) 473ml缶 [RaR Brewing / Eternal Prankster]"
    cleaned2 = pb.clean_product_title(t2)
    assert "(空輸)" not in cleaned2
    assert "ロアーブルーイング" in cleaned2
    
    # 3. Discount & Expiration
    t3 = "30%OFF【発酵芳香蒸留水プロジェクトNo.2 〜神代杉〜/醸馥(賞味期限/2026.07.08)】"
    cleaned3 = pb.clean_product_title(t3)
    assert "30%OFF" not in cleaned3
    assert "賞味期限" not in cleaned3
    assert cleaned3 == "【発酵芳香蒸留水プロジェクトNo.2 〜神代杉〜/醸馥】"
    
    # 4. Arrival schedule
    t4 = "【7/29（水）入荷予定】アドロイトセオリー オートアコースティックエミッションズ 空輸（Adroit Theory Otoacoustic Emissions）"
    cleaned4 = pb.clean_product_title(t4)
    assert "入荷予定" not in cleaned4

    # 5. Order limit & arrival schedule combined (User request bug fix)
    t5 = "【ご注文合計6本以上】ブルホス : ロンリネス 2026 | Brujos: Loneliness 2026《8/22入荷予定》"
    cleaned5 = pb.clean_product_title(t5)
    assert cleaned5 == "ブルホス : ロンリネス 2026 | Brujos: Loneliness 2026"

def test_shop_guidance():
    pb = PromptBuilder()
    guidance_volta, _ = pb.get_shop_guidance("BEER VOLTA")
    assert "BEER VOLTA" in guidance_volta or "BeerVolta" in guidance_volta
    assert "CRITICAL: Always remove volume/capacity" in guidance_volta

    guidance_chouseiya, _ = pb.get_shop_guidance("ちょうせいや")
    assert "BEFORE slash `/` is ALWAYS the Beer Name" in guidance_chouseiya

def test_build_extract_prompt():
    pb = PromptBuilder()
    prompt = pb.build_extract_prompt("ストーン : IPA | Stone: IPA 568ml", shop="BEER VOLTA")
    assert "Volume / Size Removal" in prompt
    assert "Stone: IPA 568ml" in prompt
    assert "Shop Rule" in prompt

def test_apply_product_type_override():
    pb = PromptBuilder()
    
    # 1. Other Half beer false positive 'other'
    res1 = {
        "brewery_name_jp": "Other Half", "brewery_name_en": "Other Half Brewing Co.",
        "beer_name_jp": "マイラー バッグ", "beer_name_en": "Mylar Bags",
        "product_type": "other", "is_set": False
    }
    corrected1 = pb.apply_product_type_override(res1, "[Other Half] Mylar Bags/ マイラー バッグ")
    assert corrected1["product_type"] == "beer"

    # 2. Truly non-beverage merchandise (book)
    res2 = {
        "brewery_name_jp": "", "brewery_name_en": "",
        "beer_name_jp": "", "beer_name_en": "",
        "product_type": "other", "is_set": False
    }
    corrected2 = pb.apply_product_type_override(res2, "(著者サイン入り) ベルギービール解体新書 / 山本高之 (著)")
    assert corrected2["product_type"] == "other"

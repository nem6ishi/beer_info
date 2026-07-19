#!/usr/bin/env python3
"""
ローカル Gemma 4 12B (4-bit, MLX) vs クラウド API (Gemma 4 31B)
実出力サイドバイサイド比較ベンチマークスクリプト

Usage:
  uv run python -m backend.scripts.verify_local_gemma4
"""

import os
import sys
import time
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

from google import genai
from google.genai import types as genai_types
import mlx_lm.utils

# 標準出力を強制バッファなし(または行バッファ)にする
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

# PyPI版 mlx-lm 0.31.3 等での gemma4_unified 対応パッチ
if hasattr(mlx_lm.utils, "MODEL_REMAPPING"):
    mlx_lm.utils.MODEL_REMAPPING["gemma4_unified"] = "gemma4"
    mlx_lm.utils.MODEL_REMAPPING["gemma4_text_unified"] = "gemma4_text"

try:
    from mlx_lm.models import gemma4
    _original_sanitize = getattr(gemma4.Model, "sanitize", None)
    def _patched_sanitize(self, weights):
        if _original_sanitize:
            weights = _original_sanitize(self, weights)
        if isinstance(weights, dict):
            return {k: v for k, v in weights.items() if not k.startswith("vision_embedder.") and not k.startswith("audio_embedder.")}
        elif isinstance(weights, list):
            return [(k, v) for k, v in weights if not k.startswith("vision_embedder.") and not k.startswith("audio_embedder.")]
        return weights
    gemma4.Model.sanitize = _patched_sanitize
except Exception:
    pass

from mlx_lm import load, generate
from backend.src.services.llm.gemini_extractor import GeminiExtractor

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# モデル設定
LOCAL_MODEL_NAME = "./models/gemma-4-26b-a4b-it-2bit"
API_MODEL_NAME = os.getenv("GEMINI_MODEL_ID", "gemma-4-31b-it")

# 評価用テストサンプル (難易度・バリエーション別 8件)
TEST_SAMPLES = [
    {
        "id": 1,
        "title": "うちゅうブルーイング / Uchu Brewing マーズ / MARS",
        "shop": "BEER VOLTA",
        "brewery_hint": None,
        "desc": "標準バイリンガル表記"
    },
    {
        "id": 2,
        "title": "Societe Best Friends Forever (Fremont collab) (473ml) / ベストフレンドフォエバー",
        "shop": "Antenna America",
        "brewery_hint": "Societe Brewing Company",
        "desc": "実在コラボ / 複数ブルワリー表記"
    },
    {
        "id": 3,
        "title": "ジャイガンティック サンシャインスーパースター / Gigantic Sunshine Superstar",
        "shop": "BEER VOLTA",
        "brewery_hint": "Gigantic Brewing Company",
        "desc": "カタカナ＆長文英語ビール名"
    },
    {
        "id": 4,
        "title": "【おひとり様2本限定・クール便必須】鬼伝説 金鬼ペールエール 330ml缶",
        "shop": "ちょうせいや",
        "brewery_hint": "わかさいも本舗",
        "desc": "ノイズ多数・購入制限＆クール便表記"
    },
    {
        "id": 5,
        "title": "【限定商品】志賀高原ビール / 其の十 / No.10 - 330ml",
        "shop": "BEER VOLTA",
        "brewery_hint": "玉村本店",
        "desc": "限定品・数字ネーミング"
    },
    {
        "id": 6,
        "title": "WCB / West Coast Brewing Starwatcher IPA",
        "shop": "Antenna America",
        "brewery_hint": "West Coast Brewing",
        "desc": "略称(WCB) ＋ 英語ビールタイトル"
    },
    {
        "id": 7,
        "title": "ヨロッコビール / 逗子＆鎌倉４本セット",
        "shop": "MARUHO",
        "brewery_hint": "Yorocco Beer",
        "desc": "セット商品判定 (is_set=True)"
    },
    {
        "id": 8,
        "title": "Finback Brewery / Whale Watching (TIPA)",
        "shop": "Antenna America",
        "brewery_hint": "Finback Brewery",
        "desc": "完全英語タイトル ＋ スタイル括弧表記"
    }
]


def print_header(text: str):
    print(f"\n{'='*80}", flush=True)
    print(f" {text}", flush=True)
    print(f"{'='*80}", flush=True)


def safe_parse_json(text: str, source: str) -> Optional[Dict[str, Any]]:
    """生のテキストから有効なJSONオブジェクトを網羅的に探索してパースする"""
    if not text:
        return None
    
    content = text.strip()

    # すべての { 〜 } のペアから有効な JSON を探索する
    candidates = []
    start_pos = 0
    while True:
        s = content.find("{", start_pos)
        if s == -1:
            break
        e = content.rfind("}") + 1
        while e > s:
            candidate_str = content[s:e]
            try:
                data = json.loads(candidate_str)
                if isinstance(data, dict) and ("product_type" in data or "brewery_name_en" in data or "beer_name_core" in data):
                    candidates.append((len(candidate_str), data))
                    break
            except Exception:
                pass
            e = content.rfind("}", s, e - 1) + 1
        start_pos = s + 1

    if candidates:
        # 抽出された候補の中で最も情報量（文字数）が多いJSONオブジェクトを採用する
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    
    # 候補がなければ最初の { から最後の } で json.loads のエラーログ出力
    logger.warning(f"  ❌ [{source}] 有効な JSON {{...}} が見つかりませんでした。\n     [生出力プレビュー]: {text[:300]!r}")
    return None


from mlx_lm import stream_generate
from backend.src.services.untappd.searcher import get_untappd_url
from backend.src.services.store.brewery_manager import BreweryManager


def resolve_brewery_hint(bm: BreweryManager, data: dict) -> Tuple[str, Optional[str]]:
    if not bm or not data:
        return "", None
    b_name = data.get('brewery_name_en') or data.get('brewery_name_jp') or ""
    b_url = None
    if b_name:
        b_info = bm.brewery_index.get(b_name.lower())
        if not b_info:
            found = bm.find_breweries_in_text(b_name)
            if found:
                b_info = found[0]
        if not b_info and data.get('beer_name_jp'):
            found = bm.find_breweries_in_text(data['beer_name_jp'])
            if found:
                b_info = found[0]
        if b_info:
            b_name = b_info.get('name_en') or b_name
            b_url = b_info.get('untappd_url')
    return b_name, b_url


def generate_json_fast(model, tokenizer, prompt: str, max_tokens: int = 300) -> str:
    """1トークンずつ生成し、有効なJSONが完成したか終了記号が出たら即停止(Early Stopping)する"""
    generated_text = ""
    for response in stream_generate(model, tokenizer, prompt, max_tokens=max_tokens):
        token_str = response.text
        generated_text += token_str
        
        # 不要な続き(コードブロック終了や別のチャネル開始)が出現したら即時ストップ
        if "```" in generated_text or "<|channel>" in generated_text or "<|im_end|>" in generated_text:
            break
            
        # `}` が出るたびに完成したJSONかテストして、パース成功なら即時ストップ！
        if "}" in generated_text:
            test_str = "{\n" + generated_text.split("```")[0].split("<|channel>")[0].strip()
            try:
                data = json.loads(test_str)
                if isinstance(data, dict) and "product_type" in data:
                    break
            except Exception:
                pass
                
    return generated_text


def extract_with_local_mlx(model, tokenizer, prompt: str) -> Tuple[Optional[Dict[str, Any]], float]:
    """ローカル MLX モデル (Gemma 4 12B) で推論を実行し、結果JSONと処理秒数を返す"""
    messages = [{"role": "user", "content": prompt}]
    chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    
    # Gemma 4 12B IT の思考チャネルをバイパスし、コードブロックで囲んだ純粋な JSON 出力から開始させる
    prefix = "<|channel>output\n```json\n{\n"
    chat_prompt += prefix
    
    start_time = time.time()
    try:
        raw_output = generate_json_fast(
            model,
            tokenizer,
            prompt=chat_prompt,
            max_tokens=250
        )
        elapsed = time.time() - start_time
        # クリーンアップ
        clean_out = raw_output.split("```")[0].split("<|channel>")[0].strip()
        full_json_str = "{\n" + clean_out
        logger.info(f"     [DEBUG Local MLX Fast Output ({len(raw_output)} chars, {elapsed:.2f}s)]:\n{full_json_str!r}")
        data = safe_parse_json(full_json_str, "Local MLX")
        return data, elapsed
    except Exception as e:
        logger.warning(f"  ❌ [Local MLX] 推論エラー: {e}")
        return None, time.time() - start_time


async def extract_with_cloud_api(client: genai.Client, model_id: str, prompt: str) -> Tuple[Optional[Dict[str, Any]], float]:
    """クラウド API (Gemma 4 31B) で推論を実行し、結果JSONと正味処理秒数を返す"""
    start_time = time.time()
    try:
        schema = genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "brewery_name_jp": genai_types.Schema(type=genai_types.Type.STRING, nullable=True),
                "brewery_name_en": genai_types.Schema(type=genai_types.Type.STRING, nullable=True),
                "beer_name_jp": genai_types.Schema(type=genai_types.Type.STRING, nullable=True),
                "beer_name_en": genai_types.Schema(type=genai_types.Type.STRING, nullable=True),
                "beer_name_core": genai_types.Schema(type=genai_types.Type.STRING, nullable=True),
                "search_hint": genai_types.Schema(type=genai_types.Type.STRING, nullable=True),
                "product_type": genai_types.Schema(type=genai_types.Type.STRING, enum=["beer", "set", "glass", "other"]),
                "is_set": genai_types.Schema(type=genai_types.Type.BOOLEAN),
            },
            required=["product_type", "is_set"],
        )
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=1500,
        )
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model_id,
                contents=prompt,
                config=config,
            ),
            timeout=25.0,
        )
        elapsed = time.time() - start_time
        if response.text:
            data = safe_parse_json(response.text, "Cloud API")
            return data, elapsed
        return None, elapsed
    except Exception as e:
        logger.warning(f"  ❌ [Cloud API] APIエラー: {e}")
        return None, time.time() - start_time


async def main():
    load_dotenv()
    print_header("🍻 Gemma 4 12B (Local MLX) vs Gemma 4 31B (Cloud API) 出力比較ベンチマーク")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 致命的エラー: GEMINI_API_KEY が見つかりません。", flush=True)
        sys.exit(1)
    cloud_client = genai.Client(api_key=api_key)
    extractor = GeminiExtractor()
    try:
        bm = BreweryManager()
        logger.info("🏢 BreweryManager ロード完了")
    except Exception as e:
        bm = None
        logger.warning(f"⚠️ BreweryManager ロードエラー: {e}")
    
    print(f"\n🚀 ローカル MLX モデル [{LOCAL_MODEL_NAME}] をロードしています...", flush=True)
    load_start = time.time()
    local_model, local_tokenizer = load(LOCAL_MODEL_NAME)
    load_elapsed = time.time() - load_start
    print(f"✅ ローカルモデルロード完了！ (所要時間: {load_elapsed:.2f}秒)\n", flush=True)
    
    results = []
    total_cloud_time = 0.0
    total_local_time = 0.0
    
    test_samples = TEST_SAMPLES
    for idx, sample in enumerate(test_samples, 1):
        print_header(f"サンプル #{idx}: {sample['desc']}\n  タイトル: 「{sample['title']}」")
        
        clean_title = extractor._clean_product_title(sample['title'], sample['shop'])
        hint = f"\nNote: The brewery exists and is likely: \"{sample['brewery_hint']}\"" if sample['brewery_hint'] else ""
        guidance, examples = extractor._get_shop_guidance(sample['shop'])
        prompt = extractor._build_prompt(clean_title, hint, guidance, examples)
        
        # 1. Cloud API 推論
        print(f"  ☁️  [Cloud API: {API_MODEL_NAME}] 推論中...", flush=True)
        cloud_data, cloud_time = await extract_with_cloud_api(cloud_client, API_MODEL_NAME, prompt)
        total_cloud_time += cloud_time
        print(f"     所要時間: {cloud_time:.2f}秒 | 成功: {'✅' if cloud_data else '❌'}", flush=True)
        
        # 2. Local MLX 推論
        print(f"  💻 [Local MLX: {LOCAL_MODEL_NAME}] 推論中...", flush=True)
        local_data, local_time = extract_with_local_mlx(local_model, local_tokenizer, prompt)
        total_local_time += local_time
        print(f"     所要時間: {local_time:.2f}秒 | 成功: {'✅' if local_data else '❌'}", flush=True)
        
        # 3. Enrich: Untappd アイテムの検索 (Cloud API の抽出情報を使用)
        cloud_untappd_url = "N/A"
        cloud_match_name = "N/A"
        if cloud_data and cloud_data.get('product_type') == 'beer':
            print("  🔍 [Enrich/Cloud API] 抽出情報から Untappd アイテムを検索中...", flush=True)
            c_brewery, c_url_hint = resolve_brewery_hint(bm, cloud_data)
            c_res = await get_untappd_url(
                brewery_name=c_brewery or cloud_data.get('brewery_name_en') or cloud_data.get('brewery_name_jp') or "",
                beer_name=cloud_data.get('beer_name_en') or cloud_data.get('beer_name_jp') or "",
                beer_name_jp=cloud_data.get('beer_name_jp'),
                brewery_url=c_url_hint,
                search_hint=cloud_data.get('search_hint'),
                beer_name_core=cloud_data.get('beer_name_core')
            )
            if c_res.get('success') and c_res.get('url'):
                cloud_untappd_url = c_res.get('url')
                cloud_match_name = c_res.get('beer_name', 'Found')
            else:
                cloud_untappd_url = f"NotFound ({c_res.get('failure_reason', 'unknown')})"

        # 4. Enrich: Untappd アイテムの検索 (Local MLX の抽出情報を使用)
        local_untappd_url = "N/A"
        local_match_name = "N/A"
        if local_data and local_data.get('product_type') == 'beer':
            print("  🔍 [Enrich/Local MLX] 抽出情報から Untappd アイテムを検索中...", flush=True)
            l_brewery, l_url_hint = resolve_brewery_hint(bm, local_data)
            l_res = await get_untappd_url(
                brewery_name=l_brewery or local_data.get('brewery_name_en') or local_data.get('brewery_name_jp') or "",
                beer_name=local_data.get('beer_name_en') or local_data.get('beer_name_jp') or "",
                beer_name_jp=local_data.get('beer_name_jp'),
                brewery_url=l_url_hint,
                search_hint=local_data.get('search_hint'),
                beer_name_core=local_data.get('beer_name_core')
            )
            if l_res.get('success') and l_res.get('url'):
                local_untappd_url = l_res.get('url')
                local_match_name = l_res.get('beer_name', 'Found')
            else:
                local_untappd_url = f"NotFound ({l_res.get('failure_reason', 'unknown')})"

        # 横並び表示
        print(f"\n  📊 【抽出結果＆Enrich アイテム検索 サイドバイサイド比較】", flush=True)
        print(f"  {'項目':<18} | {'☁️ Cloud API (31B)':<28} | {'💻 Local MLX (12B 4-bit)':<28}", flush=True)
        print(f"  {'-'*18}-+-{'-'*28}-+-{'-'*28}", flush=True)
        
        fields_to_compare = [
            ("brewery_name_en", "英語ブルワリー名"),
            ("brewery_name_jp", "和名ブルワリー名"),
            ("beer_name_core",  "ビールコア名"),
            ("search_hint",     "検索ヒント"),
            ("product_type",    "商品区分 (beer等)"),
            ("is_set",          "セット商品 (bool)"),
        ]
        
        for key, label in fields_to_compare:
            c_val = str(cloud_data.get(key, 'N/A')) if cloud_data else 'ERR'
            l_val = str(local_data.get(key, 'N/A')) if local_data else 'ERR'
            if len(c_val) > 26: c_val = c_val[:24] + ".."
            if len(l_val) > 26: l_val = l_val[:24] + ".."
            match_mark = "⭕" if c_val == l_val and c_val != 'ERR' else ("⚠️" if c_val != l_val else "❌")
            print(f"  {label:<16} | {c_val:<28} | {l_val:<28} {match_mark}", flush=True)
            
        print(f"  {'-'*18}-+-{'-'*28}-+-{'-'*28}", flush=True)
        c_u_disp = cloud_untappd_url[:26] + ".." if len(cloud_untappd_url) > 28 else cloud_untappd_url
        l_u_disp = local_untappd_url[:26] + ".." if len(local_untappd_url) > 28 else local_untappd_url
        u_match = "⭕" if cloud_untappd_url == local_untappd_url and "http" in cloud_untappd_url else ("⚠️" if cloud_untappd_url != local_untappd_url else "❌")
        print(f"  {'🍺 Untappd URL':<16} | {c_u_disp:<28} | {l_u_disp:<28} {u_match}", flush=True)
        if "http" in cloud_untappd_url or "http" in local_untappd_url:
            print(f"  {'   (マッチアイテム)':<16} | {cloud_match_name[:26]:<28} | {local_match_name[:26]:<28}", flush=True)
            
        results.append({
            "sample": sample,
            "cloud_data": cloud_data,
            "cloud_time": cloud_time,
            "cloud_untappd_url": cloud_untappd_url,
            "cloud_match_name": cloud_match_name,
            "local_data": local_data,
            "local_time": local_time,
            "local_untappd_url": local_untappd_url,
            "local_match_name": local_match_name,
        })
        
        if idx < len(test_samples):
            await asyncio.sleep(2.0)

    # 総合ベンチマーク結果の出力
    print_header("📈 ベンチマーク最終サマリー")
    avg_cloud = total_cloud_time / max(len(test_samples), 1)
    avg_local = total_local_time / max(len(test_samples), 1)
    print(f"  テスト件数            : {len(test_samples)} 件", flush=True)
    print(f"  ☁️  Cloud API 平均速度  : {avg_cloud:.2f} 秒/件 (合計: {total_cloud_time:.2f}秒)", flush=True)
    print(f"  💻 Local MLX 平均速度  : {avg_local:.2f} 秒/件 (合計: {total_local_time:.2f}秒)", flush=True)
    if avg_local > 0:
        print(f"  ⚡ スピード比較          : Local MLX は Cloud API と比べて 1件あたり {avg_cloud - avg_local:+.2f} 秒", flush=True)
    
    # 比較結果の詳細を Markdown レポートとしても書き出し
    report_path = "backend/scripts/gemma4_comparison_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Gemma 4 12B (Local MLX) vs Gemma 4 31B (Cloud API) 抽出＆Enrich結果比較レポート\n\n")
        f.write(f"- **測定日時**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **ローカルモデル**: `{LOCAL_MODEL_NAME}` (初回ロード時間: {load_elapsed:.2f}秒)\n")
        f.write(f"- **クラウドモデル**: `{API_MODEL_NAME}`\n")
        f.write(f"- **平均処理速度**: Cloud `{avg_cloud:.2f}秒/件` vs Local `{avg_local:.2f}秒/件`\n\n")
        
        f.write("## 個別詳細テーブル\n\n")
        for r in results:
            s = r["sample"]
            c = r["cloud_data"] or {}
            l = r["local_data"] or {}
            f.write(f"### #{s['id']}. {s['desc']}\n")
            f.write(f"- **タイトル**: 「`{s['title']}`」 (ショップ: `{s['shop']}`)\n")
            f.write(f"- **処理時間**: Cloud `{r['cloud_time']:.2f}秒` vs Local `{r['local_time']:.2f}秒`\n\n")
            f.write("| 項目 | Cloud API (31B) | Local MLX (12B 4-bit) | 判定 |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            for key, label in fields_to_compare:
                c_val = str(c.get(key, 'N/A'))
                l_val = str(l.get(key, 'N/A'))
                mark = "⭕ 一致" if c_val == l_val and c_val != 'N/A' else ("⚠️ 差異" if c_val != l_val else "❌")
                f.write(f"| {label} (`{key}`) | `{c_val}` | `{l_val}` | {mark} |\n")
            
            # Enrich 結果の追記
            c_url = r.get("cloud_untappd_url", "N/A")
            l_url = r.get("local_untappd_url", "N/A")
            c_name = r.get("cloud_match_name", "N/A")
            l_name = r.get("local_match_name", "N/A")
            url_mark = "⭕ 一致" if c_url == l_url and "http" in c_url else ("⚠️ 差異" if c_url != l_url else "❌")
            c_url_fmt = f"[{c_url}]({c_url})" if "http" in c_url else f"`{c_url}`"
            l_url_fmt = f"[{l_url}]({l_url})" if "http" in l_url else f"`{l_url}`"
            f.write(f"| **🍺 Untappd URL** | {c_url_fmt} | {l_url_fmt} | **{url_mark}** |\n")
            if "http" in c_url or "http" in l_url:
                f.write(f"| *(マッチアイテム)* | `{c_name}` | `{l_name}` | -\n")
            f.write("\n")
            
    print(f"\n📄 詳細な Markdown 比較レポートを `{report_path}` に保存しました！", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

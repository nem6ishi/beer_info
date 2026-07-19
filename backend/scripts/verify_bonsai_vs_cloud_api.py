#!/usr/bin/env python3
"""
ローカル MLX (prism-ml/Ternary-Bonsai-27B-mlx-2bit) vs クラウド API (Gemma 4 31B)
実出力サイドバイサイド比較＆LLM API代用可否検証ベンチマークスクリプト

Usage:
  uv run python -m backend.scripts.verify_bonsai_vs_cloud_api
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
from mlx_lm import load, stream_generate
from backend.src.services.llm.gemini_extractor import GeminiExtractor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

LOCAL_MODEL_NAME = "prism-ml/Ternary-Bonsai-27B-mlx-2bit"
API_MODEL_NAME = os.getenv("GEMINI_MODEL_ID", "gemma-4-31b-it")

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
    if not text:
        return None
    content = text.strip()
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
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return None

def extract_with_local_bonsai(model, tokenizer, prompt: str) -> Tuple[Optional[Dict[str, Any]], float, int]:
    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        chat_prompt = f"User: {prompt}\nAssistant:\n"
    
    # 思考プロセスをスキップし、即座に正確な構造化JSONの出力を開始させるプリフィックス注入
    json_prefix = "```json\n{\n"
    chat_prompt += json_prefix
    
    start_time = time.perf_counter()
    generated_text = "{\n"
    token_count = 0
    try:
        for response in stream_generate(model, tokenizer, chat_prompt, max_tokens=1500):
            token_str = response.text
            generated_text += token_str
            token_count += 1
            
            # 終了記号(```やチャネル終了)が出現したら即時ストップ
            if "```" in token_str or "<|im_end|>" in token_str or "<|channel>" in token_str:
                break
            
            # `}` が出るたびにパーステストを行い、完全なJSONになったら Early Stopping!
            if "}" in generated_text:
                test_str = generated_text.split("```")[0].split("<|im_end|>")[0].strip()
                try:
                    data = json.loads(test_str)
                    if isinstance(data, dict) and "product_type" in data and "is_set" in data:
                        break
                except Exception:
                    pass
                    
        elapsed = time.perf_counter() - start_time
        data = safe_parse_json(generated_text, "Local Bonsai 27B")
        return data, elapsed, token_count
    except Exception as e:
        logger.warning(f"  ❌ [Local Bonsai] 推論エラー: {e}")
        return None, time.perf_counter() - start_time, token_count

async def extract_with_cloud_api(client: genai.Client, model_id: str, prompt: str) -> Tuple[Optional[Dict[str, Any]], float]:
    start_time = time.perf_counter()
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
        elapsed = time.perf_counter() - start_time
        if response.text:
            data = safe_parse_json(response.text, "Cloud API")
            return data, elapsed
        return None, elapsed
    except Exception as e:
        logger.warning(f"  ❌ [Cloud API] APIエラー: {e}")
        return None, time.perf_counter() - start_time

async def main():
    load_dotenv()
    print_header("🍻 Bonsai 27B (Local MLX) vs Gemma 4 31B (Cloud API) LLM API 代用可否ベンチマーク")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY が見つかりません。", flush=True)
        sys.exit(1)
    cloud_client = genai.Client(api_key=api_key)
    extractor = GeminiExtractor()
    
    print(f"\n🌿 ローカル MLX モデル [{LOCAL_MODEL_NAME}] をロード中...", flush=True)
    load_start = time.perf_counter()
    try:
        local_model, local_tokenizer = load(LOCAL_MODEL_NAME)
        load_time = time.perf_counter() - load_start
        print(f"✅ ローカルモデルロード完了 (所要時間: {load_time:.2f}秒)", flush=True)
    except Exception as e:
        print(f"❌ ローカルモデルのロードに失敗しました: {e}", flush=True)
        sys.exit(1)

    results = []
    
    for sample in TEST_SAMPLES:
        sid = sample["id"]
        title = sample["title"]
        shop = sample["shop"]
        hint = sample["brewery_hint"]
        desc = sample["desc"]
        
        print_header(f"テスト #{sid}: {desc}\n📦 商品名: 「{title}」 (Shop: {shop})")
        
        guidance, examples = extractor._get_shop_guidance(shop)
        prompt = extractor._build_prompt(title, hint or "なし", guidance, examples)
        
        # --- 1. Cloud API ---
        print("⏳ [1/2] Cloud API (Gemma 4 31B) にリクエスト送信中...", flush=True)
        cloud_json, cloud_time = await extract_with_cloud_api(cloud_client, API_MODEL_NAME, prompt)
        
        # --- 2. Local Bonsai ---
        print("⏳ [2/2] Local Bonsai 27B (MLX 2bit) で推論実行中...", flush=True)
        local_json, local_time, local_tokens = extract_with_local_bonsai(local_model, local_tokenizer, prompt)
        tps = local_tokens / local_time if local_time > 0 else 0
        
        # 結果表示
        print("\n" + "-"*80, flush=True)
        print(f"☁️  Cloud API (Gemma 4 31B) [{cloud_time:.2f}秒]:", flush=True)
        print(json.dumps(cloud_json, ensure_ascii=False, indent=2) if cloud_json else "❌ パース失敗/タイムアウト", flush=True)
        print("-" * 80, flush=True)
        print(f"🌿 Local Bonsai 27B (MLX 2bit) [{local_time:.2f}秒 | {tps:.1f} tok/s]:", flush=True)
        print(json.dumps(local_json, ensure_ascii=False, indent=2) if local_json else "❌ パース失敗", flush=True)
        print("-" * 80, flush=True)
        
        results.append({
            "id": sid,
            "title": title,
            "desc": desc,
            "cloud_json": cloud_json,
            "cloud_time": cloud_time,
            "local_json": local_json,
            "local_time": local_time,
            "local_tps": tps
        })

    # レポート保存
    report_path = "backend/scripts/bonsai_vs_cloud_api_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 🍻 Bonsai 27B (Local MLX) vs Gemma 4 31B (Cloud API) LLM API 代用可否ベンチマーク\n\n")
        f.write("## 概要\n")
        f.write("- **ローカルモデル**: `prism-ml/Ternary-Bonsai-27B-mlx-2bit` (Apple Silicon MLX, 2bit)\n")
        f.write("- **クラウドAPI**: `Gemma-4-31B-it` (Google Gemini API Structured JSON)\n")
        f.write("- **テスト件数**: 難易度・バリエーション別 8サンプル\n\n")
        
        f.write("## 比較サマリー表\n\n")
        f.write("| ID | サンプル概要 | Cloud API 判定 | Local Bonsai 判定 | Cloud 時間 | Local 時間 | Local 速度 |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        
        local_success = 0
        for r in results:
            c_type = r['cloud_json'].get('product_type') if r['cloud_json'] else "N/A"
            l_type = r['local_json'].get('product_type') if r['local_json'] else "N/A"
            if r['local_json']:
                local_success += 1
            f.write(f"| #{r['id']} | {r['desc']} | `{c_type}` | `{l_type}` | {r['cloud_time']:.2f}s | {r['local_time']:.2f}s | {r['local_tps']:.1f} tok/s |\n")
            
        f.write(f"\n- **パース成功率**: Cloud API: {sum(1 for r in results if r['cloud_json'])}/8, Local Bonsai: {local_success}/8\n\n")
        f.write("## 詳細結果\n\n")
        for r in results:
            f.write(f"### テスト #{r['id']}: {r['title']} ({r['desc']})\n\n")
            f.write("#### ☁️ Cloud API (Gemma 4 31B)\n```json\n")
            f.write(json.dumps(r['cloud_json'], ensure_ascii=False, indent=2) if r['cloud_json'] else "{}")
            f.write("\n```\n\n#### 🌿 Local Bonsai 27B\n```json\n")
            f.write(json.dumps(r['local_json'], ensure_ascii=False, indent=2) if r['local_json'] else "{}")
            f.write("\n```\n---\n")

    print_header(f"✨ ベンチマーク完了！ 詳細レポートを保存しました: {report_path}")

if __name__ == "__main__":
    asyncio.run(main())

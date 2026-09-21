#!/usr/bin/env python3
"""
ローカル MLX 2bit モデル: prism-ml/Ternary-Bonsai-2-27B-mlx-2bit (Bonsai 2)
動作検証＆ビール情報抽出ベンチマークスクリプト

Usage:
  uv run python -m backend.scripts.verify_local_bonsai2
"""

import os
import sys

# XetHubクライアントのCLOSE_WAITハングバグを回避するため無効化
os.environ["HF_HUB_DISABLE_XET"] = "1"

import time
import json
import logging
from pathlib import Path
from huggingface_hub import snapshot_download

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MODEL_REPO = "prism-ml/Ternary-Bonsai-2-27B-mlx-2bit"

def run_verification():
    logger.info("=" * 70)
    logger.info("🌿 [Bonsai 2 (27B) Local MLX] 動作検証＆情報抽出テスト")
    logger.info(f"📦 ターゲットリポジトリ: {MODEL_REPO}")
    logger.info("=" * 70)

    logger.info("\n⏳ 1. モデルファイルを確認/ダウンロード中 (初回は約8.6GBをダウンロード)...")
    start_dl = time.perf_counter()
    try:
        model_dir = snapshot_download(
            repo_id=MODEL_REPO,
            allow_patterns=["*.json", "*.safetensors", "*.jinja", "runtime/*", "README.md", "PACK-RUNTIME.md"],
            resume_download=True
        )
        dl_time = time.perf_counter() - start_dl
        logger.info(f"✅ ダウンロード/キャッシュ確認完了 ({dl_time:.2f} 秒): {model_dir}")
    except Exception as e:
        logger.error(f"❌ ダウンロードエラー: {e}")
        return

    # 同梱ランタイムをロード
    runtime_dir = Path(model_dir) / "runtime"
    if str(runtime_dir) not in sys.path:
        sys.path.insert(0, str(runtime_dir))

    logger.info("\n⏳ 2. Bonsai 2 専用ランタイムからモデルをロード中...")
    start_load = time.perf_counter()
    try:
        from vision_artifact import load_vl_model, chat_config
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        model, processor, config = load_vl_model(model_dir)
        load_time = time.perf_counter() - start_load
        logger.info(f"✅ モデルロード完了！ 所要時間: {load_time:.2f} 秒\n")
    except Exception as e:
        logger.error(f"❌ モデルロードエラー: {e}")
        logger.exception(e)
        return

    # テスト対象の商品名リスト
    test_cases = [
        "【West Coast Brewing】 Starwatcher (West Coast IPA / ABV 7.0%) 500ml缶",
        "うちゅうブルーイング / MARS (マーズ) 宇宙IPA 350ml 缶",
    ]

    for i, product_name in enumerate(test_cases, 1):
        logger.info(f"\n🚀 3.{i} 推論テスト: 「{product_name}」")
        prompt_text = (
            "あなたはクラフトビール専門のAIアシスタントです。\n"
            "以下の商品タイトルから、「ブルワリー名」「ビール名」「スタイル」「ABV(アルコール度数)」「セットかどうか」を正確に抽出してJSONで答えてください。\n"
            "余計な解説は含めず、有効なJSONオブジェクトのみを出力してください。\n\n"
            f"商品タイトル: {product_name}\n\n"
            "JSON出力:"
        )

        formatted_prompt = apply_chat_template(processor, chat_config(config), prompt_text, num_images=0)
        formatted_prompt += "```json\n{\n"

        start_gen = time.perf_counter()
        try:
            # Instructモード用の推奨パラメータ: temp=0.7
            gen_result = generate(
                model=model,
                processor=processor,
                prompt=formatted_prompt,
                max_tokens=300,
                temperature=0.7,
                verbose=False
            )
            gen_time = time.perf_counter() - start_gen

            output_text = gen_result.text if hasattr(gen_result, "text") else str(gen_result)
            gen_tps = getattr(gen_result, "generation_tps", 0.0)
            gen_tokens = getattr(gen_result, "generation_tokens", 0)

            full_json_str = "{\n" + output_text.split("```")[0].strip()
            logger.info(f"⏱️ 推論所要時間: {gen_time:.2f} 秒 (生成速度: {gen_tps:.2f} tok/s, {gen_tokens} tokens)")
            logger.info(f"📄 生の生成出力:\n{full_json_str}")

            try:
                parsed = json.loads(full_json_str)
                logger.info("✅ JSONパース成功:")
                logger.info(json.dumps(parsed, ensure_ascii=False, indent=2))
            except Exception as pe:
                logger.warning(f"⚠️ JSONパース警告: {pe}")

        except Exception as e:
            logger.error(f"❌ 推論エラー: {e}")
            logger.exception(e)

    logger.info("\n" + "=" * 70)
    logger.info("🎉 全テスト完了！")
    logger.info("=" * 70)

if __name__ == "__main__":
    run_verification()

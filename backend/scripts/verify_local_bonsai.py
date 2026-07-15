#!/usr/bin/env python3
"""
ローカル MLX 2bit モデル: prism-ml/Ternary-Bonsai-27B-mlx-2bit
Mac M1 16GB での動作検証＆スピードベンチマークスクリプト

Usage:
  uv run python -m backend.scripts.verify_local_bonsai
"""

import os
import sys
import time
import logging
from mlx_lm import load, generate

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

MODEL_ID = "prism-ml/Ternary-Bonsai-27B-mlx-2bit"

def verify_bonsai_inference():
    logger.info("=" * 65)
    logger.info(f"🌿 [Bonsai 27B Local MLX] 動作検証＆スピードテスト")
    logger.info(f"📦 ターゲットモデル: {MODEL_ID}")
    logger.info("=" * 65)
    
    logger.info("\n⏳ 1. モデルとトークナイザーをロード中 (初回はHuggingFaceから自動ダウンロードされます約8.5GB)...")
    start_load = time.perf_counter()
    try:
        model, tokenizer = load(MODEL_ID)
        load_time = time.perf_counter() - start_load
        logger.info(f"✅ ロード完了！ 所要時間: {load_time:.2f} 秒\n")
    except Exception as e:
        logger.error(f"❌ [ロードエラー]: {e}")
        return

    # テストプロンプト
    prompt_text = (
        "あなたはクラフトビール専門のAIアシスタントです。\n"
        "以下の商品タイトルから、「ブルワリー名」「ビール名」「スタイル」「ABV(アルコール度数)」「セットかどうか」を正確に抽出してJSONで答えてください。\n\n"
        "商品タイトル: 【West Coast Brewing】 Starwatcher (West Coast IPA / ABV 7.0%) 500ml缶\n\n"
        "JSON出力:"
    )
    
    # チャットテンプレート適用
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        messages = [{"role": "user", "content": prompt_text}]
        formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        formatted_prompt = f"User: {prompt_text}\nAssistant:\n"

    logger.info("🚀 2. 推論開始...")
    logger.info(f"--- 入力プロンプト ---\n{prompt_text}\n-----------------------")
    
    start_gen = time.perf_counter()
    try:
        response = generate(
            model=model,
            tokenizer=tokenizer,
            prompt=formatted_prompt,
            max_tokens=256,
            verbose=True
        )
        gen_time = time.perf_counter() - start_gen
        logger.info("\n" + "=" * 65)
        logger.info(f"✨ [推論成功] 総所要時間: {gen_time:.2f} 秒")
        logger.info("=" * 65)
    except Exception as e:
        logger.error(f"\n❌ [推論エラー]: {e}")

if __name__ == "__main__":
    verify_bonsai_inference()

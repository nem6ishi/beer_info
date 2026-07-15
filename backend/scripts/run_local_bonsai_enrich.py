#!/usr/bin/env python3
"""
ローカル MLX (prism-ml/Ternary-Bonsai-27B-mlx-2bit) による
未enrich＆再挑戦アイテム全自動 Enrich バッチスクリプト
(caffeinate -i -s 対応: Macの画面を閉じても夜間バックグラウンドで動き続ける仕様)

Usage:
  # 画面を閉じても動かし続ける場合 (おすすめ)
  caffeinate -i -s uv run python -m backend.scripts.run_local_bonsai_enrich --batch-size 500

  # 通常実行
  uv run python -m backend.scripts.run_local_bonsai_enrich --batch-size 100
"""

import os
import sys
import time
import json
import logging
import argparse
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

from mlx_lm import load, stream_generate
from backend.src.core.db import get_supabase_client, refresh_materialized_view
from backend.src.services.gemini.extractor import GeminiExtractor
from backend.src.services.untappd.searcher import get_untappd_url
from backend.scripts.verify_local_gemma4 import BreweryManager, resolve_brewery_hint

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bonsai_enrich")

LOCAL_MODEL_NAME = "prism-ml/Ternary-Bonsai-27B-mlx-2bit"

def safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
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

def extract_with_local_bonsai(model, tokenizer, prompt: str) -> Tuple[Optional[Dict[str, Any]], float]:
    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        chat_prompt = f"User: {prompt}\nAssistant:\n"
    
    # 思考バイパス＆高速ダイレクトJSON出力プリフィックス注入
    json_prefix = "```json\n{\n"
    chat_prompt += json_prefix
    
    start_time = time.perf_counter()
    generated_text = "{\n"
    try:
        for response in stream_generate(model, tokenizer, chat_prompt, max_tokens=1500):
            token_str = response.text
            generated_text += token_str
            
            if "```" in token_str or "<|im_end|>" in token_str or "<|channel>" in token_str:
                break
            
            if "}" in generated_text:
                test_str = generated_text.split("```")[0].split("<|im_end|>")[0].strip()
                try:
                    data = json.loads(test_str)
                    if isinstance(data, dict) and "product_type" in data and "is_set" in data:
                        break
                except Exception:
                    pass
        elapsed = time.perf_counter() - start_time
        data = safe_parse_json(generated_text)
        return data, elapsed
    except Exception as e:
        logger.warning(f"  ❌ [Bonsai] 推論エラー: {e}")
        return None, time.perf_counter() - start_time

async def main():
    parser = argparse.ArgumentParser(description="Run Local Bonsai 27B Enrichment Pipeline")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of items to process in this run")
    parser.add_argument("--offset", type=int, default=0, help="Offset for target items")
    parser.add_argument("--target", choices=["missing_gemini", "missing_untappd", "all_missing"], default="all_missing", help="Target criteria")
    args = parser.parse_args()

    load_dotenv()
    logger.info("🌿 Starting Local Bonsai 27B Enrichment Pipeline...")
    logger.info(f"⚙️ Target: {args.target} | Batch Size: {args.batch_size} | Offset: {args.offset}")

    supabase = get_supabase_client()
    if not supabase:
        logger.error("❌ Supabase client initialization failed.")
        sys.exit(1)

    # 1. ターゲットの取得
    logger.info("🔍 DBから未Enrich対象アイテムを取得中...")
    
    # 1. ターゲットの取得: AIでビール(product_type='beer')と判定済みだが untappd_url が null のアイテムを最優先取得
    logger.info("🔍 DBから「AIでビールと判定済みだが未紐付け」のアイテムを取得中...")
    res = supabase.table('gemini_data').select('url, product_type, untappd_url, brewery_name_en, beer_name_en, search_hint') \
                  .eq('product_type', 'beer').is_('untappd_url', 'null') \
                  .limit(args.batch_size).offset(args.offset).execute()
    
    target_urls = [r['url'] for r in (res.data or [])]
    
    # URL から scraped_beers の商品名(name)やショップ(shop)をバルク取得
    scraped_map = {}
    if target_urls:
        for i in range(0, len(target_urls), 200):
            chunk = target_urls[i:i+200]
            s_res = supabase.table('scraped_beers').select('url, name, shop').in_('url', chunk).execute()
            for sr in (s_res.data or []):
                scraped_map[sr['url']] = sr

    target_items = []
    for r in (res.data or []):
        url = r['url']
        s_info = scraped_map.get(url, {})
        target_items.append({
            'url': url,
            'title': s_info.get('name') or r.get('beer_name_en') or 'Unknown Title',
            'shop': s_info.get('shop') or 'Unknown Shop',
            'brewery_hint': r.get('brewery_name_en'),
            'untappd_url': None,
            'product_type': 'beer'
        })

    logger.info(f"🎯 対象アイテム取得完了: 合計 {len(target_items)} 件")
    if not target_items:
        logger.info("✨ 処理対象がありません！完了です。")
        return

    # 2. BreweryManager と Bonsai モデルロード
    try:
        bm = BreweryManager()
    except Exception as e:
        bm = None
        logger.warning(f"⚠️ BreweryManager ロード失敗: {e}")

    logger.info(f"🌿 ローカル MLX モデル [{LOCAL_MODEL_NAME}] をロード中...")
    model, tokenizer = load(LOCAL_MODEL_NAME)
    logger.info("✅ モデルロード完了！処理を開始します。")

    extractor = GeminiExtractor()
    success_untappd = 0
    processed = 0

    for idx, item in enumerate(target_items, 1):
        url = item['url']
        title = item.get('title') or item.get('name') or "Unknown Title"
        shop = item.get('shop') or "Unknown Shop"
        hint = item.get('brewery_hint')

        logger.info(f"\n--------------------------------------------------------------------------------")
        logger.info(f"📦 [{idx}/{len(target_items)}] 処理中: 「{title}」 (Shop: {shop})")
        
        guidance, examples = extractor._get_shop_guidance(shop)
        prompt = extractor._build_prompt(title, hint or "なし", guidance, examples)

        # 1. Bonsai で抽出
        bonsai_data, elapsed = extract_with_local_bonsai(model, tokenizer, prompt)
        if not bonsai_data:
            logger.warning(f"  ❌ [{elapsed:.1f}s] Bonsai 抽出失敗/パースエラー。スキップします。")
            continue

        prod_type = bonsai_data.get('product_type', 'beer')
        is_set = bonsai_data.get('is_set', False)
        logger.info(f"  🌿 Bonsai 抽出成功 [{elapsed:.1f}s]: type={prod_type}, set={is_set}")
        logger.info(f"     brewery_en={bonsai_data.get('brewery_name_en')}, core={bonsai_data.get('beer_name_core')}, hint={bonsai_data.get('search_hint')}")

        # 非ビールやセット品は untappd_url=None で DB を更新
        if prod_type != 'beer' or is_set:
            logger.info(f"  🛡️ ビール以外のアイテム ({prod_type}) として gemini_data を更新・整理します。")
            gemini_payload = {
                'url': url,
                'brewery_name_jp': bonsai_data.get('brewery_name_jp'),
                'brewery_name_en': bonsai_data.get('brewery_name_en'),
                'beer_name_jp': bonsai_data.get('beer_name_jp'),
                'beer_name_en': bonsai_data.get('beer_name_en'),
                'beer_name_core': bonsai_data.get('beer_name_core'),
                'search_hint': bonsai_data.get('search_hint'),
                'product_type': prod_type,
                'is_set': is_set,
                'untappd_url': None,
                'payload': f"```json\n{json.dumps(bonsai_data, ensure_ascii=False, indent=2)}\n```"
            }
            supabase.table('gemini_data').upsert(gemini_payload, on_conflict='url').execute()
            # scraped_beers も整理
            supabase.table('scraped_beers').update({'untappd_url': None}).eq('url', url).execute()
            processed += 1
            continue

        # 2. Untappd 検索実行
        l_brewery, l_url_hint = resolve_brewery_hint(bm, bonsai_data)
        logger.info("  🔍 Untappd データベース/Web を検索中...")
        res_u = await get_untappd_url(
            brewery_name=l_brewery or bonsai_data.get('brewery_name_en') or bonsai_data.get('brewery_name_jp') or "",
            beer_name=bonsai_data.get('beer_name_en') or bonsai_data.get('beer_name_jp') or "",
            beer_name_jp=bonsai_data.get('beer_name_jp'),
            brewery_url=l_url_hint,
            search_hint=bonsai_data.get('search_hint'),
            beer_name_core=bonsai_data.get('beer_name_core')
        )

        found_url = None
        if res_u.get('success') and res_u.get('url'):
            found_url = res_u.get('url')
            match_name = res_u.get('beer_name', 'Found')
            logger.info(f"  🎉 Untappd 検索成功！！ => {found_url} ({match_name})")
            success_untappd += 1
        else:
            logger.info(f"  ⚠️ Untappd 未発見 ({res_u.get('failure_reason', 'unknown')})")

        # 3. DB 更新保存 (gemini_data ＆ scraped_beers)
        gemini_payload = {
            'url': url,
            'brewery_name_jp': bonsai_data.get('brewery_name_jp'),
            'brewery_name_en': bonsai_data.get('brewery_name_en'),
            'beer_name_jp': bonsai_data.get('beer_name_jp'),
            'beer_name_en': bonsai_data.get('beer_name_en'),
            'beer_name_core': bonsai_data.get('beer_name_core'),
            'search_hint': bonsai_data.get('search_hint'),
            'product_type': prod_type,
            'is_set': is_set,
            'untappd_url': found_url,
            'payload': f"```json\n{json.dumps(bonsai_data, ensure_ascii=False, indent=2)}\n```"
        }
        supabase.table('gemini_data').upsert(gemini_payload, on_conflict='url').execute()
        if found_url:
            supabase.table('scraped_beers').update({'untappd_url': found_url}).eq('url', url).execute()

        processed += 1
        
        # 10件ごとにマテリアライズドビューをリフレッシュ
        if processed % 10 == 0:
            logger.info("  🔄 マテリアライズドビュー beer_info_view を更新中...")
            refresh_materialized_view(supabase, logger)

    # 最終リフレッシュ
    logger.info("\n================================================================----------------")
    logger.info(f"✨ バッチ完了！ 処理完了: {processed}件 | Untappd新規発見: {success_untappd}件")
    logger.info("🔄 最終マテリアライズドビュー更新...")
    refresh_materialized_view(supabase, logger)
    logger.info("🍻 すべての処理が完了しました！")

if __name__ == "__main__":
    asyncio.run(main())

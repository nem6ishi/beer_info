#!/usr/bin/env python3
import os
import sys
import time
import json
import logging
import argparse
import asyncio
import re
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

from mlx_lm import load, stream_generate
from backend.src.core.db import get_supabase_client
from backend.src.services.llm.gemini_extractor import GeminiExtractor
from backend.src.services.untappd.searcher import get_untappd_url
from backend.src.services.untappd.http_client import scrape_beer_details
from backend.scripts.verify_local_gemma4 import BreweryManager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("local_pipeline")

LOCAL_MODEL_NAME = "prism-ml/Ternary-Bonsai-27B-mlx-2bit"
set_pattern = re.compile(r'(\d+本(?:パック|セット|アソート|飲み比べ)|\d+\s*Cans?\s*(?:Set|Pack)|\d+\s*Bottles?\s*(?:Set|Pack)|飲み比べ|アソート|お試しセット|本セット|缶セット|Variety\s*Pack)', re.IGNORECASE)
glass_pattern = re.compile(r'(グラス|Glass|Tシャツ|パーカー|アパレル|キャップ|グラスセット)', re.IGNORECASE)

def safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text: return None
    content = text.strip()
    start_pos = 0
    while True:
        s = content.find("{", start_pos)
        if s == -1: break
        e = content.rfind("}") + 1
        while e > s:
            candidate_str = content[s:e]
            try:
                data = json.loads(candidate_str)
                if isinstance(data, dict):
                    return data
            except Exception: pass
            e = content.rfind("}", s, e - 1) + 1
        start_pos = s + 1
    return None

def extract_with_local_bonsai(model, tokenizer, prompt: str) -> Tuple[Optional[Dict[str, Any]], float]:
    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        chat_prompt = f"User: {prompt}\nAssistant:\n"
    
    chat_prompt += "```json\n{\n"
    start_time = time.perf_counter()
    generated_text = "{\n"
    try:
        for response in stream_generate(model, tokenizer, chat_prompt, max_tokens=1500):
            token_str = response.text
            generated_text += token_str
            if "```" in token_str or "<|im_end|>" in token_str: break
            if "}" in generated_text:
                test_str = generated_text.split("```")[0].split("<|im_end|>")[0].strip()
                try:
                    data = json.loads(test_str)
                    if isinstance(data, dict) and "product_type" in data and "is_set" in data:
                        break
                except Exception: pass
        elapsed = time.perf_counter() - start_time
        return safe_parse_json(generated_text), elapsed
    except Exception as e:
        logger.warning(f"  ❌ [Bonsai] 推論エラー: {e}")
        return None, 0.0

def select_candidate_with_local_bonsai(model, tokenizer, product_name: str, brewery: str, beer_name: str, candidates: list) -> int:
    prompt = f"""You are a beer matching assistant.
Find the BEST matching beer from the Search Candidates for the Target Product.
It doesn't have to be a "perfect" string match, but it should represent the exact same product. Use the Original Title as your primary context.

Target Product Info:
- Original Title: "{product_name}"
- Extracted Brewery: "{brewery}"
- Extracted Beer Name: "{beer_name}"

Search Candidates:
"""
    for i, c in enumerate(candidates):
        prompt += f"[{i}] Brewery: {c.get('brewery_name', '')} | Beer: {c.get('beer_name', '')} | URL: {c.get('url', '')}\n"
        
    prompt += """
Output ONLY the index number (0, 1, 2...) of the best match. If NONE of the candidates match, output -1. Do not output anything else.
Index:"""
    
    messages = [{"role": "user", "content": prompt}]
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        chat_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        chat_prompt = f"User: {prompt}\nAssistant:\n"
        
    try:
        response = ""
        for r in stream_generate(model, tokenizer, chat_prompt, max_tokens=20):
            response += r.text
            if "```" in response or "<|im_end|>" in response: break
        
        match = re.search(r'-?\d+', response)
        if match:
            idx = int(match.group())
            if -1 <= idx < len(candidates):
                return idx
        return -1
    except Exception as e:
        logger.warning(f"  ❌ [Bonsai Selection] エラー: {e}")
        return -1

async def process_single_item(item: Dict[str, Any], model, tokenizer, bm, extractor, supabase):
    url = item['url']
    title = item.get('title') or item.get('name') or "Unknown Title"
    shop = item.get('shop') or "Unknown Shop"
    hint = item.get('brewery_hint')

    logger.info(f"\n--------------------------------------------------------------------------------")
    logger.info(f"📦 処理中: 「{title}」 (Shop: {shop})")

    if set_pattern.search(title) or glass_pattern.search(title):
        ptype = 'set' if set_pattern.search(title) else 'glass'
        logger.info(f"  ⏭️ [事前スキップ] {ptype.upper()}として検知: {title}")
        supabase.table('gemini_data').upsert({'url': url, 'product_type': ptype, 'is_set': ptype=='set'}).execute()
        supabase.table('scraped_beers').update({'untappd_url': 'skipped'}).eq('url', url).execute()
        return

    guidance, examples = extractor._get_shop_guidance(shop)
    prompt = extractor._build_prompt(title, hint or "なし", guidance, examples)
    bonsai_data, elapsed = extract_with_local_bonsai(model, tokenizer, prompt)
    
    if not bonsai_data:
        logger.warning(f"  ❌ 抽出失敗。スキップします。")
        return

    prod_type = bonsai_data.get('product_type', 'beer')
    is_set = bonsai_data.get('is_set', False)
    b_en = bonsai_data.get('brewery_name_en')
    b_jp = bonsai_data.get('brewery_name_jp')
    beer_en = bonsai_data.get('beer_name_en')
    beer_jp = bonsai_data.get('beer_name_jp')
    core = bonsai_data.get('beer_name_core')
    s_hint = bonsai_data.get('search_hint')

    logger.info(f"  🌿 抽出成功 [{elapsed:.1f}s]: brewery={b_en}, core={core}")

    if prod_type != 'beer' or is_set or not b_en or not core:
        logger.info(f"  🛡️ ビール以外または情報不足 ({prod_type}) のため検索をスキップします。")
        supabase.table('gemini_data').upsert({'url': url, **bonsai_data}).execute()
        supabase.table('scraped_beers').update({'untappd_url': 'skipped'}).eq('url', url).execute()
        return

    logger.info("  🔍 Untappd データベース/Web を検索中...")
    search_res = await get_untappd_url(
        brewery_name=b_en,
        beer_name=core,
        beer_name_jp=beer_jp,
        search_hint=s_hint,
        beer_name_core=core,
        original_title=title,
        skip_llm=True,
        return_candidates=True
    )

    final_untappd_url = None
    if search_res.get('success') and search_res.get('url'):
        final_untappd_url = search_res['url']
        logger.info(f"  🎉 1発ヒット！ => {final_untappd_url}")
    elif search_res.get('candidates'):
        candidates = search_res['candidates']
        logger.info(f"  🤖 候補が {len(candidates)} 件あります。ローカルLLMで判定します...")
        idx = select_candidate_with_local_bonsai(model, tokenizer, title, b_en, core, candidates)
        if idx != -1:
            final_untappd_url = candidates[idx].get('url')
            logger.info(f"  ✅ [Bonsai Selection] 選ばれた候補 [{idx}]: {final_untappd_url}")
        else:
            logger.info("  ❌ [Bonsai Selection] 該当する候補なし (-1)")

    supabase.table('gemini_data').upsert({'url': url, 'untappd_url': final_untappd_url, **bonsai_data}).execute()
    
    if final_untappd_url:
        supabase.table('scraped_beers').update({'untappd_url': final_untappd_url}).eq('url', url).execute()
        try:
            details = await scrape_beer_details(final_untappd_url)
            if details:
                from backend.src.commands.enrich_untappd import map_details_to_payload
                payload = map_details_to_payload(details)
                payload['untappd_url'] = final_untappd_url
                supabase.table('untappd_data').upsert(payload).execute()
                logger.info(f"  📥 Untappd詳細情報を保存しました")
        except Exception as e:
            logger.warning(f"  ⚠️ Untappd詳細の取得に失敗: {e}")
    else:
        supabase.table('scraped_beers').update({'untappd_url': 'no_results'}).eq('url', url).execute()
        logger.info("  ⚠️ 最終的に紐付け失敗 (no_results) として保存しました")

async def main():
    parser = argparse.ArgumentParser(description="Local end-to-end pipeline with Bonsai")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--shop", type=str, help="Target specific shop")
    args = parser.parse_args()

    load_dotenv()
    supabase = get_supabase_client()
    
    target_items = []
    
    if args.shop:
        logger.info(f"🔍 DBから「{args.shop}」の未紐付けアイテムを取得中...")
        res = supabase.table('scraped_beers').select('url, name, shop').eq('shop', args.shop).is_('untappd_url', 'null').limit(args.batch_size).offset(args.offset).execute()
        for r in (res.data or []):
            target_items.append({
                'url': r['url'],
                'title': r['name'] or 'Unknown Title',
                'shop': r['shop'] or 'Unknown Shop',
                'brewery_hint': None,
            })
    else:
        logger.info("🔍 DBから未紐付けのアイテムを取得中...")
        res = supabase.table('scraped_beers').select('url, name, shop').is_('untappd_url', 'null').limit(args.batch_size).offset(args.offset).execute()
        for r in (res.data or []):
            target_items.append({
                'url': r['url'],
                'title': r['name'] or 'Unknown Title',
                'shop': r['shop'] or 'Unknown Shop',
                'brewery_hint': None,
            })

    logger.info(f"🎯 対象アイテム取得完了: 合計 {len(target_items)} 件")
    if not target_items: return

    try: bm = BreweryManager()
    except Exception: bm = None

    logger.info(f"🌿 ローカル MLX モデル [{LOCAL_MODEL_NAME}] をロード中...")
    model, tokenizer = load(LOCAL_MODEL_NAME)
    logger.info("✅ モデルロード完了！処理を開始します。")

    extractor = GeminiExtractor()

    for item in target_items:
        await process_single_item(item, model, tokenizer, bm, extractor, supabase)

if __name__ == "__main__":
    asyncio.run(main())

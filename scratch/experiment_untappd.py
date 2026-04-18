import os
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any
from google import genai
from supabase import create_client, Client
from dotenv import load_dotenv
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Supabase setup
sb_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
sb_key = os.getenv("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(sb_url, sb_key)

# Gemini setup
gemini_key = os.getenv("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=gemini_key)
# MODEL_ID = "gemini-2.0-flash" # Use a fast model for experiment
MODEL_ID = "gemma-4-31b-it" # As per extractor.py config

async def clean_and_classify(product_name: str) -> Dict[str, Any]:
    """Use Gemini to clean product name and identify if it's a beer/set/glass."""
    prompt = f"""
    Analyze this craft beer shop product name and extract clean information.
    Product: "{product_name}"

    Identify:
    1. Clean Brewery Name (English if possible)
    2. Clean Beer Name (English if possible, remove sale prefixes like 40%OFF)
    3. Product Type: "beer", "set", "glass", "other"
    4. Search Query: A 3-4 word query optimized for Untappd.

    Output JSON:
    {{
      "brewery": "...",
      "beer_name": "...",
      "product_type": "...",
      "search_query": "..."
    }}
    """
    
    try:
        response = gemini_client.models.generate_content(model=MODEL_ID, contents=prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini cleaning failed: {e}")
        return {"product_type": "beer", "search_query": product_name}

def search_untappd_broad(query: str) -> List[Dict[str, str]]:
    """Broad search using DuckDuckGo for untappd links."""
    search_q = f"site:untappd.com/b/ {query}"
    logger.info(f"  Searching DDG: {search_q}")
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(search_q, max_results=3):
                if "untappd.com/b/" in r['href']:
                    results.append({
                        "title": r['title'],
                        "href": r['href'],
                        "body": r['body']
                    })
    except Exception as e:
        logger.error(f"DDG search failed: {e}")
    return results

async def match_results(product_name: str, results: List[Dict[str, str]]) -> Optional[str]:
    """Let Gemini decide which search result is the correct Untappd URL."""
    if not results:
        return None
    
    results_str = "\n".join([f"{i+1}. {r['title']} - {r['href']}\n   Snippet: {r['body']}" for i, r in enumerate(results)])
    
    prompt = f"""
    Identify the correct Untappd beer URL for the product: "{product_name}"
    
    Search Results:
    {results_str}
    
    Compare the brewery and beer name. 
    Output the index (1, 2, 3) of the correct match, or "none" if no match is certain.
    Format your response as a JSON: {{"match_index": 1}} or {{"match_index": null}}
    """
    
    try:
        response = gemini_client.models.generate_content(model=MODEL_ID, contents=prompt)
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        data = json.loads(text)
        idx = data.get("match_index")
        if idx and 1 <= idx <= len(results):
            return results[idx-1]['href']
    except Exception as e:
        logger.error(f"Gemini matching failed: {e}")
    return None

async def experiment_item(item: Dict[str, Any]):
    logger.info(f"Target: {item['name']} (Shop: {item['shop']})")
    
    # 1. Clean and Classify
    info = await clean_and_classify(item['name'])
    logger.info(f"  Classified as: {info['product_type']} | Query: {info['search_query']}")
    
    if info['product_type'] != 'beer':
        logger.info(f"  ⏩ Skipping {info['product_type']}")
        return {"status": "skipped", "type": info['product_type']}
    
    # 2. Broad Search
    search_results = search_untappd_broad(info['search_query'])
    
    # 3. LLM Match
    match_url = await match_results(item['name'], search_results)
    
    if match_url:
        logger.info(f"  ✅ Match Found: {match_url}")
        return {"status": "found", "url": match_url}
    else:
        logger.info(f"  ❌ No Match Found")
        return {"status": "not_found"}

async def main():
    # Target 5 specific items identified earlier
    targets = [
        {"shop": "ちょうせいや", "name": "在庫整理(残り僅か) 40%OFF【ライシングクライム/富士桜高原麦酒】"},
        {"shop": "アローム", "name": "マルール ブリュット グラス 150cc [Malheur BRUT glazen]"},
        {"shop": "一期一会～る", "name": "ジューシーブルーイング　2023年7月来日　ヘイジーIPA4種セット（Juicy Brewing HAZY SET）"},
        {"shop": "ちょうせいや", "name": "在庫整理(残り僅か) 30%OFF【丹波路ピルスナー/丹波路ブルワリー】"},
        {"shop": "アローム", "name": "マルール 12 [Malheur 12] 330ml"}
    ]
    
    results = []
    for item in targets:
        res = await experiment_item(item)
        results.append({"item": item['name'], "result": res})
        await asyncio.sleep(2) # Avoid rate limits
    
    print("\n" + "="*50)
    print("EXPERIMENT RESULTS")
    print("="*50)
    for r in results:
        status = r['result']['status']
        detail = r['result'].get('url') or r['result'].get('type') or ""
        print(f"{r['item'][:40] + '...' if len(r['item']) > 40 else r['item']}: {status.upper()} ({detail})")

if __name__ == "__main__":
    asyncio.run(main())

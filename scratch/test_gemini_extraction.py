import asyncio
import os
import json
from backend.src.services.gemini.extractor import GeminiExtractor

async def test_extraction():
    extractor = GeminiExtractor()
    test_cases = [
        {
            "shop": "一期一会～る",
            "title": "エブリウェアー エブリシングオールウェイズ（Everywhere Brewing Everything Always）"
        },
        {
            "shop": "ちょうせいや",
            "title": "【BATON 005(インペリアルスタウト＋青山椒)375ml/箕面ビール】"
        },
        {
            "shop": "BEER VOLTA",
            "title": "バテレ ボルドウィニー / Vertere Baldwinii 350ml"
        }
    ]
    
    for case in test_cases:
        print(f"\n--- Testing {case['shop']} ---")
        print(f"Title: {case['title']}")
        result = await extractor.extract_info(case['title'], case['shop'])
        print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    asyncio.run(test_extraction())

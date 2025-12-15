
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.gemini_extractor import GeminiExtractor

async def test_extraction():
    load_dotenv()
    
    extractor = GeminiExtractor()
    if not extractor.client:
        print("Gemini API Key not found. Skipping test.")
        return

    test_cases = [
        "【TECHNO PILS/FETISH CLUB】",
        "West Coast IPA / Green Cheek Beer Co.",
        "【UCHU BREWING/AMRTA】",
        "ナマチャン やみつきエール ブラックペッパー / NAMACHAN American IPA w/Black Paper"
    ]

    print("Running Extraction Tests...\n")

    for case in test_cases:
        print(f"Input: {case}")
        result = await extractor.extract_info(case)
        print(f"Result: {result}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_extraction())

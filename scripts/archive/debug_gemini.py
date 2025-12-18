
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv
from app.services.gemini_extractor import GeminiExtractor

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

async def test_extraction():
    extractor = GeminiExtractor()
    product_name = "ブラックタイド x ヤッホーブルーイング ブラックデーモン / BLACK TIDE x Yoho Brewing Black Demon　≪12/20-21入荷予定≫"
    
    print(f"Testing extraction for: {product_name}")
    result = await extractor.extract_info(product_name)
    print("Result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_extraction())


import os
import asyncio
from google import genai
from dotenv import load_dotenv

load_dotenv()

import pytest

@pytest.mark.asyncio
async def test_gemma():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)
    model_id = "gemma-3-27b-it" 
    print(f"🤖 Testing model: {model_id} ...")

    prompt = """
    Extract the brewery name and beer name from the following product title string.
    Separate them into Japanese and English versions if present.
    Product Title: "うちゅうブルーイング / Uchu Brewing マーズ / MARS"
    
    Return ONLY a raw JSON string (no markdown formatting, no code blocks) with strictly these keys:
    - "brewery_name_jp"
    - "brewery_name_en"
    - "beer_name_jp"
    - "beer_name_en"
    """

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            # Removed config with response_mime_type="application/json" as it's not supported
        )

        if response.text:
            print("✅ Success! Response:")
            print(response.text)
        else:
            print("⚠️ No text returned.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemma())

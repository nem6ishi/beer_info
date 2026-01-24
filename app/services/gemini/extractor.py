import os
import json
import time
import asyncio
from typing import Optional, Dict
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class GeminiExtractor:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY not found. Extraction will be disabled.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)
        
        
        # Rate Limiting Configuration
        self.last_request_time = 0
        self.daily_request_count = 0
        
        # Model Priority & Configuration based on Quotas (2025-12-08)
        # 1. Gemma 3 27B: 30 RPM, 14,400 RPD (Massive capacity, Primary)
        # 2. Flash Lite: 10 RPM, 20 RPD (Very limited daily stub)
        # 3. Flash: 5 RPM, 20 RPD (Very limited daily stub)
        self.models = [
            {"id": "gemma-3-27b-it", "interval": 2.0, "json_mode": False, "daily_limit": 14400}, # 30 RPM = 2s
            {"id": "gemini-2.5-flash-lite", "interval": 6.0, "json_mode": True, "daily_limit": 20}, # 10 RPM = 6s
            {"id": "gemini-2.5-flash", "interval": 12.0, "json_mode": True, "daily_limit": 20}  # 5 RPM = 12s
        ]
        self.daily_limit = 14400  # Global limit effectively tied to Gemma

    async def _generate_content_with_retry(self, prompt: str):
        """
        Attempts to generate content using models in priority order.
        Falls back to the next model if a Rate Limit (429) is encountered.
        """
        for i, model_config in enumerate(self.models):
            model_id = model_config["id"]
            interval = model_config["interval"]
            use_json_mode = model_config["json_mode"]

            # Enforce Rate Limit (per-model interval approach or shared)
            # For simplicity, we enforce the interval of the *current* model before calling it
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < interval:
                wait_time = interval - time_since_last
                # Only wait if it's significant, otherwise just go (burst tolerance)
                if wait_time > 0.1:
                    print(f"  [Gemini] Waiting {wait_time:.2f}s for {model_id}...")
                    await asyncio.sleep(wait_time)

            try:
                print(f"  [Gemini] Calling {model_id}...")
                
                # Configure generation
                gen_config = None
                if use_json_mode:
                    gen_config = types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )

                response = self.client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=gen_config
                )
                
                self.last_request_time = time.time()
                self.daily_request_count += 1
                
                if response.text:
                    if not use_json_mode:
                        # Clean up code blocks if Gemma returns Markdown
                        text = response.text.strip()
                        if text.startswith("```json"):
                            text = text[7:]
                        if text.startswith("```"):
                            text = text[3:]
                        if text.endswith("```"):
                            text = text[:-3]
                        return json.loads(text.strip())
                    else:
                        return json.loads(response.text)
                
            except Exception as e:
                error_str = str(e)
                self.last_request_time = time.time() # Update time even on failure
                
                if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                    print(f"  [Gemini] ⚠️ Rate limit hit on {model_id}")
                    # If this is not the last model, continue to next loop iteration (fallback)
                    if i < len(self.models) - 1:
                        print(f"  [Gemini] 🔄 Switching to next model...")
                        await asyncio.sleep(1) # Brief pause before switch
                        continue
                    else:
                        print(f"  [Gemini] ❌ All models exhausted rate limits.")
                        raise Exception("RATE_LIMIT_EXHAUSTED_ALL_MODELS")
                else:
                    # Non-rate-limit error (e.g. 400 Bad Request), invalid JSON, etc.
                    print(f"  [Gemini] ❌ Error with {model_id}: {e}")
                    # Decide if we want to skip to next model or fail hard. 
                    # Usually 400s don't get fixed by switching models (unless it's config related),
                    # but 500s might. For now, we continue to try fallback for robustness.
                    if i < len(self.models) - 1:
                        print(f"  [Gemini] 🔄 Switching to next model...")
                        await asyncio.sleep(1)
                        continue
                    raise e
        
        return None

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Extracts brewery and beer name using the multi-model fallback strategy.
        """
        if not self.client:
            return {"brewery_name_jp": None, "brewery_name_en": None, 
                    "beer_name_jp": None, "beer_name_en": None}

        if self.daily_request_count >= self.daily_limit:
            print(f"[Gemini] Daily limit reached ({self.daily_limit}). Skipping.")
            return {"brewery_name_jp": None, "brewery_name_en": None, 
                    "beer_name_jp": None, "beer_name_en": None}

        brewery_hint = ""
        if known_brewery:
            print(f"[Gemini] Extracting: {product_name} (Hint: {known_brewery})")
            brewery_hint = f"\nNote: The brewery name is likely: \"{known_brewery}\""
        else:
            print(f"[Gemini] Extracting: {product_name}")

        prompt = f"""
        Extract the brewery name and beer name from the following product title string.
        Separate them into Japanese and English versions if present.
        Also determine the product type: "beer", "set", "glass", or "other".
        Product Title: "{product_name}"{brewery_hint}

        Guidelines for names:
        - Identify the brewery name and beer name from the title.
        - **COLLABORATIONS**: If multiple breweries are involved (often separated by 'x', '×', or '/'), include all of them in the brewery name (e.g., "Totopia x Teenage").
        - **FORMATS**: 
            - Common formats include "Beer Name / Brewery Name" or "【Beer Name / Brewery Name】".
            - If the title follows "【A/B】", A is typically the Beer Name and B is the Brewery Name.
            - However, if B looks like a beer name and A is a known brewery (from hints or context), adjust accordingly.
        - **HINTS**: Use the provided brewery hints if they match parts of the title. If multiple hints are given, it's likely a collaboration.
        - **NOISE REMOVAL**: Strictly REMOVE text like "Arrival Date", "Sold Out", "One per person", "Air Import" (空輸), "≪...入荷≫", "【...入荷予定】".
        
        Guidelines for product_type:
        - "beer": A single beer product (including 4-pack/6-pack of the SAME beer).
        - "set": Multiple DIFFERENT beers, variety packs.
        - "glass": Glassware.
        - "other": Merchandise.

        Return ONLY a raw JSON string with strictly these keys:
        - "brewery_name_jp" (Japanese brewery name, or null)
        - "brewery_name_en" (English brewery name, or null)
        - "beer_name_jp" (Japanese beer name, or null)
        - "beer_name_en" (English beer name, or null)
        - "product_type" (string: "beer", "set", "glass", or "other")
        - "is_set" (boolean, true ONLY if product_type is "set")
        
        Examples:
        1. Input: "Theory of Clarity / Inkhorn Brewing"
           Output: {{"brewery_name_jp": "インクホーン", "brewery_name_en": "Inkhorn Brewing", "beer_name_jp": null, "beer_name_en": "Theory of Clarity", "product_type": "beer", "is_set": false}}
        
        2. Input: "【Tonephilia/Totopia×Teenage】" (Wait, Hint: Totopia, Teenage)
           Output: {{"brewery_name_jp": "トートピア x ティーネイジ", "brewery_name_en": "Totopia x Teenage", "beer_name_jp": "トーンフィリア", "beer_name_en": "Tonephilia", "product_type": "beer", "is_set": false}}
        """

        try:
            data = await self._generate_content_with_retry(prompt)
            if data:
                print(f"[Gemini] ✅ Success. Daily usage: {self.daily_request_count}/{self.daily_limit}")
                return {
                    "brewery_name_jp": data.get("brewery_name_jp"),
                    "brewery_name_en": data.get("brewery_name_en"),
                    "beer_name_jp": data.get("beer_name_jp"),
                    "beer_name_en": data.get("beer_name_en"),
                    "product_type": data.get("product_type", "beer"),
                    "is_set": data.get("is_set", False)
                }
        except Exception as e:
            print(f"[Gemini] Extraction failed: {e}")

        return {
            "brewery_name_jp": None, 
            "brewery_name_en": None, 
            "beer_name_jp": None, 
            "beer_name_en": None,
            "product_type": "beer",
            "is_set": False
        }

# Usage Example:
# extractor = GeminiExtractor()
# info = await extractor.extract_info("West Coast IPA / Green Cheek Beer Co.")

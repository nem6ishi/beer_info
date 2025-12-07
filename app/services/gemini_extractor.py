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
        # Based on actual API quotas (as of 2025-12-07):
        # gemini-2.5-flash-lite: 10 RPM, 250K TPM, 20 RPD
        # gemini-2.5-flash: 5 RPM, 250K TPM, 20 RPD
        
        self.last_request_time = 0
        self.daily_request_count = 0
        
        # Model Configuration (start with flash-lite)
        self.model_id = "gemini-2.5-flash-lite"
        self.request_interval = 6.0  # 10 RPM = 60s / 10 = 6s per request
        self.daily_limit = 20  # 20 RPD (shared across both models)

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Extracts brewery and beer name from the product string using Gemini.
        Enforces rate limiting internally.
        Automatically switches to gemini-2.5-flash if rate limit is hit.
        """
        if not self.client:
            return {"brewery_name_jp": None, "brewery_name_en": None, 
                    "beer_name_jp": None, "beer_name_en": None}

        # Check daily limit
        if self.daily_request_count >= self.daily_limit:
            print(f"[Gemini] Daily limit reached ({self.daily_limit} requests). Skipping.")
            return {"brewery_name_jp": None, "brewery_name_en": None, 
                    "beer_name_jp": None, "beer_name_en": None}

        # Enforce Rate Limit (15 RPM = 4s per request)
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            print(f"[Gemini] Rate limit: Waiting {wait_time:.2f}s...")
            await asyncio.sleep(wait_time)

        try:
            if known_brewery:
                print(f"[Gemini] Extracting for: {product_name} (Hint: {known_brewery})")
            else:
                print(f"[Gemini] Extracting for: {product_name}")
            
            # Build prompt with optional brewery hint
            brewery_hint = ""
            if known_brewery:
                brewery_hint = f"\nNote: The brewery name is likely: \"{known_brewery}\""
            
            prompt = f"""
            Extract the brewery name and beer name from the following product title string.
            Separate them into Japanese and English versions if present.
            Product Title: "{product_name}"{brewery_hint}
            
            Return ONLY a JSON object with strictly these keys:
            - "brewery_name_jp" (Japanese brewery name, or null)
            - "brewery_name_en" (English brewery name, or null)
            - "beer_name_jp" (Japanese beer name, or null)
            - "beer_name_en" (English beer name, or null)
            
            Example:
            {{
              "brewery_name_jp": "インクホーン",
              "brewery_name_en": "Inkhorn Brewing",
              "beer_name_jp": "鶯",
              "beer_name_en": "UGUISU"
            }}
            """

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            self.last_request_time = time.time()
            self.daily_request_count += 1
            
            if response.text:
                data = json.loads(response.text)
                print(f"[Gemini] Daily usage: {self.daily_request_count}/{self.daily_limit}")
                return {
                    "brewery_name_jp": data.get("brewery_name_jp"),
                    "brewery_name_en": data.get("brewery_name_en"),
                    "beer_name_jp": data.get("beer_name_jp"),
                    "beer_name_en": data.get("beer_name_en")
                }
            
        except Exception as e:
            error_str = str(e)
            
            # Check if it's a rate limit error (429 RESOURCE_EXHAUSTED)
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                print(f"[Gemini] Rate limit hit on {self.model_id}")
                
                # Switch to gemini-2.5-flash if currently using flash-lite
                if self.model_id == "gemini-2.5-flash-lite":
                    print(f"[Gemini] Switching to gemini-2.5-flash...")
                    self.model_id = "gemini-2.5-flash"
                    self.request_interval = 12.0  # 5 RPM = 60s / 5 = 12s per request
                    
                    # Retry with new model
                    try:
                        await asyncio.sleep(2)  # Brief wait before retry
                        
                        response = self.client.models.generate_content(
                            model=self.model_id,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )
                        
                        self.last_request_time = time.time()
                        self.daily_request_count += 1
                        
                        if response.text:
                            data = json.loads(response.text)
                            print(f"[Gemini] ✅ Success with {self.model_id}")
                            return {
                                "brewery_name_jp": data.get("brewery_name_jp"),
                                "brewery_name_en": data.get("brewery_name_en"),
                                "beer_name_jp": data.get("beer_name_jp"),
                                "beer_name_en": data.get("beer_name_en")
                            }
                    except Exception as retry_error:
                        retry_error_str = str(retry_error)
                        # If fallback model also hits rate limit, raise exception
                        if "429" in retry_error_str and "RESOURCE_EXHAUSTED" in retry_error_str:
                            print(f"[Gemini] ❌ Rate limit hit on fallback model {self.model_id}")
                            raise Exception(f"RATE_LIMIT_EXHAUSTED: Both models hit rate limit")
                        else:
                            print(f"[Gemini] Error with {self.model_id}: {retry_error}")
                else:
                    # Already using fallback model and hit rate limit again
                    print(f"[Gemini] ❌ Already using {self.model_id}, rate limit exhausted")
                    raise Exception(f"RATE_LIMIT_EXHAUSTED: {self.model_id} hit rate limit")
            else:
                print(f"[Gemini] Error extracting info: {e}")
            
            # Ensure we update last request time even on error to prevent bursting
            self.last_request_time = time.time()
            self.daily_request_count += 1
            
        return {
            "brewery_name_jp": None, 
            "brewery_name_en": None, 
            "beer_name_jp": None, 
            "beer_name_en": None
        }

# Usage Example:
# extractor = GeminiExtractor()
# info = await extractor.extract_info("West Coast IPA / Green Cheek Beer Co.")

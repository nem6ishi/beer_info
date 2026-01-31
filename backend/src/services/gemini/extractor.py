import os
import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class GeminiExtractor:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Extraction will be disabled.")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)
        
        # Load shop rules from external JSON
        self.shop_rules = self._load_shop_rules()
        
        # Rate Limiting Configuration
        self.last_request_time = 0
        self.daily_request_count = 0
        
        # Model Priority & Configuration
        # 1. Gemma 3 27B: 30 RPM, 14,400 RPD (Primary)
        # 2. Flash Lite: 10 RPM, 20 RPD (Stub)
        # 3. Flash: 5 RPM, 20 RPD (Stub)
        self.models = [
            {"id": "gemma-3-27b-it", "interval": 3.0, "json_mode": False, "daily_limit": 14400},
            {"id": "gemini-2.5-flash-lite", "interval": 6.0, "json_mode": True, "daily_limit": 20},
            {"id": "gemini-2.5-flash", "interval": 12.0, "json_mode": True, "daily_limit": 20}
        ]
        self.global_daily_limit = 14400

    def _load_shop_rules(self) -> Dict[str, Any]:
        """Loads shop-specific rules from JSON file."""
        try:
            json_path = os.path.join(os.path.dirname(__file__), "shop_rules.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            logger.warning(f"Shop rules file not found: {json_path}")
        except Exception as e:
            logger.error(f"Failed to load shop rules: {e}")
        return {}

    async def _generate_content_with_retry(self, prompt: str) -> Optional[Dict[str, Any]]:
        # ... (rest of the method remains the same)
        """Attempts to generate content using models in priority order with fallback."""
        for i, config in enumerate(self.models):
            model_id = config["id"]
            interval = config["interval"]
            use_json_mode = config["json_mode"]

            # Rate Limit Throttle
            await self._throttle(interval, model_id)

            try:
                logger.info(f"  [Gemini] Calling {model_id}...")
                
                gen_config = types.GenerateContentConfig(
                    response_mime_type="application/json"
                ) if use_json_mode else None

                response = self.client.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=gen_config
                )
                
                self.last_request_time = time.time()
                self.daily_request_count += 1
                
                if response.text:
                    return self._parse_json_response(response.text, sanitize=not use_json_mode)
                
            except Exception as e:
                if self._should_fallback(e, i):
                    logger.warning(f"  [Gemini] ⚠️ Rate limit or transient error on {model_id}. Switching...")
                    await asyncio.sleep(1)
                    continue
                raise e
        
        return None

    async def _throttle(self, interval: float, model_id: str):
        """Simple rate limit delay."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < interval:
            wait_time = interval - time_since_last
            if wait_time > 0.1:
                logger.debug(f"  [Gemini] Waiting {wait_time:.2f}s for {model_id}...")
                await asyncio.sleep(wait_time)

    def _should_fallback(self, error: Exception, current_index: int) -> bool:
        """Determines if we should try the next model."""
        error_str = str(error)
        is_last_model = current_index >= len(self.models) - 1
        
        if is_last_model:
            return False
            
        # Fallback on rate limits or internal errors
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            return True
        if "500" in error_str or "Internal Server Error" in error_str:
            return True
            
        return False

    def _parse_json_response(self, text: str, sanitize: bool = False) -> Optional[Dict[str, Any]]:
        """Parses JSON from response text, optionally cleaning markdown blocks."""
        try:
            content = text.strip()
            if sanitize:
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            
            data = json.loads(content)
            if isinstance(data, dict):
                data["raw_response"] = text
            return data
        except Exception as e:
            logger.error(f"  [Gemini] Failed to parse JSON: {e}")
            return None

    def _get_shop_guidance(self, shop: Optional[str]) -> tuple[str, str]:
        """Provides specific formatting rules and examples based on the shop."""
        guidance = ""
        examples = ""

        if shop and self.shop_rules and shop in self.shop_rules:
            target = self.shop_rules[shop]
            guidance = target.get("rule", "")
            examples = target.get("examples", "")

        return guidance, examples

    def _build_prompt(self, product_name: str, brewery_hint: str, shop_guidance: str, examples: str) -> str:
        """Constructs the full extraction prompt."""
        return f"""
        Extract brewery and beer names from the product title.
        Identify product type: "beer", "set", "glass", or "other".
        Product Title: "{product_name}"
        {brewery_hint}

        Rules:
        - **Format**: In "【A/B】", A is Beer Name and B is Brewery Name.
        {shop_guidance}
        - **Collab**: If multiple breweries are involved (×, &, /), include all (e.g., "A x B").
        - **Clean**: Remove "Sold Out", "入荷", "ml缶", "【クール便】", "【限定品】" etc.
        - **Product Type**: "beer" (single/pack), "set" (variety), "glass", "other".

        Output JSON:
        {{
          "brewery_name_jp": "...", "brewery_name_en": "...",
          "beer_name_jp": "...", "beer_name_en": "...",
          "product_type": "...", "is_set": boolean
        }}

        Example:
        {examples if examples else '1. "Beer Name / Brewery" -> {"brewery_name_en": "Brewery", "beer_name_en": "Beer Name", "product_type": "beer"}'}
        """

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point for extracting beer information."""
        if not self.client or self.daily_request_count >= self.global_daily_limit:
            return self._empty_result()

        logger.info(f"[Gemini] Extracting: {product_name} (Known: {known_brewery}, Shop: {shop})")

        hint = f"\nNote: The brewery exists and is likely: \"{known_brewery}\"" if known_brewery else ""
        guidance, examples = self._get_shop_guidance(shop)
        prompt = self._build_prompt(product_name, hint, guidance, examples)

        logger.debug(f"[Gemini] Full Prompt:\n{'-'*40}\n{prompt}\n{'-'*40}")

        try:
            data = await self._generate_content_with_retry(prompt)
            if data:
                logger.info(f"  ✅ Extraction Success:")
                logger.info(f"     - Brewery: {data.get('brewery_name_en')} ({data.get('brewery_name_jp')})")
                logger.info(f"     - Beer:    {data.get('beer_name_en')} ({data.get('beer_name_jp')})")
                logger.info(f"     - Type:    {data.get('product_type')} (Set: {data.get('is_set')})")
                
                logger.debug(f"[Gemini] Success. Daily usage: {self.daily_request_count}/{self.global_daily_limit}")
                res = {
                    "brewery_name_jp": data.get("brewery_name_jp"),
                    "brewery_name_en": data.get("brewery_name_en"),
                    "beer_name_jp": data.get("beer_name_jp"),
                    "beer_name_en": data.get("beer_name_en"),
                    "product_type": data.get("product_type", "beer"),
                    "is_set": data.get("is_set", False),
                    "raw_response": data.get("raw_response")
                }
                return res
        except Exception as e:
            logger.error(f"[Gemini] Extraction failed: {e}")

        return self._empty_result()

    def _empty_result(self) -> Dict[str, Any]:
        """Returns a default empty result structure."""
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

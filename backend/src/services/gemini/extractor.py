import os
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple, cast
from google import genai
from google.genai.types import GenerateContentConfig
from dotenv import load_dotenv
from ...core.types import GeminiExtraction

load_dotenv()

logger = logging.getLogger(__name__)

class GeminiExtractor:
    client: Optional[genai.Client]
    shop_rules: Dict[str, Any]
    last_request_time: float
    daily_request_count: int
    model_id: str
    fallback_model_id: str
    model_interval: float
    global_daily_limit: int

    def __init__(self) -> None:
        api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
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
        
        # Model Configuration: Gemma 4 31B (15 RPM, 1,500 RPD)
        self.model_id = "gemma-4-31b-it"
        self.fallback_model_id = "gemma-4-26b-a4b-it"
        self.model_interval = 3.0
        self.global_daily_limit = 14400

    def _load_shop_rules(self) -> Dict[str, Any]:
        """Loads shop-specific rules from JSON file."""
        try:
            json_path: str = os.path.join(os.path.dirname(__file__), "shop_rules.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    return cast(Dict[str, Any], json.load(f))
            logger.warning(f"Shop rules file not found: {json_path}")
        except Exception as e:
            logger.error(f"Failed to load shop rules: {e}")
        return {}

    async def _generate_content(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Generates content using the configured Gemma model with fallback."""
        if not self.client:
            return None

        try:
            await self._throttle(self.model_interval, self.model_id)

            logger.info(f"  [Gemini] Calling {self.model_id}...")
            response: Any = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
        except Exception as e:
            error_msg: str = str(e).lower()
            if getattr(e, 'code', None) == 429 or "exhausted" in error_msg or "quota" in error_msg or "unavailable" in error_msg:
                if self.model_id != self.fallback_model_id:
                    logger.warning(f"  [Gemini] {self.model_id} limit reached or unavailable. Falling back to {self.fallback_model_id}")
                    self.model_id = self.fallback_model_id
                    await self._throttle(self.model_interval, self.model_id)
                    logger.info(f"  [Gemini] Calling fallback {self.model_id}...")
                    response = self.client.models.generate_content(
                        model=self.model_id,
                        contents=prompt
                    )
                else:
                    raise
            else:
                raise
        
        self.last_request_time = time.time()
        self.daily_request_count += 1
        
        if response.text:
            return self._parse_json_response(response.text, sanitize=True)
        
        return None

    async def _throttle(self, interval: float, model_id: str) -> None:
        """Simple rate limit delay."""
        current_time: float = time.time()
        time_since_last: float = current_time - self.last_request_time
        if time_since_last < interval:
            wait_time: float = interval - time_since_last
            if wait_time > 0.1:
                logger.debug(f"  [Gemini] Waiting {wait_time:.2f}s for {model_id}...")
                await asyncio.sleep(wait_time)

    def _parse_json_response(self, text: str, sanitize: bool = False) -> Optional[Dict[str, Any]]:
        """Parses JSON from response text, optionally cleaning markdown blocks."""
        try:
            content: str = text.strip()
            if sanitize:
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            
            data: Any = json.loads(content)
            if isinstance(data, dict):
                data["raw_response"] = text
            return data
        except Exception as e:
            logger.error(f"  [Gemini] Failed to parse JSON: {e}")
            return None

    def _get_shop_guidance(self, shop: Optional[str]) -> Tuple[str, str]:
        """Provides specific formatting rules and examples based on the shop."""
        guidance: str = ""
        examples: str = ""

        if shop and self.shop_rules and shop in self.shop_rules:
            target: Dict[str, Any] = self.shop_rules[shop]
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
        - **brewery_name_jp**: Preserve the original Japanese brewery name as-is (e.g., "ヨロッコ", "家守堂").
        - **brewery_name_en**: Use the brewery's OFFICIAL English/romanized name if known (e.g., "Yorocco Beer" for ヨロッコ, "Yamorido" for 家守堂). For Japanese-only breweries, use phonetic romanization (NOT semantic translation). WRONG: "Root + Branch Brewing" for ヨロッコ. RIGHT: "Yorocco Beer".
        - **beer_name_core**: The essential/searchable part of the beer name. Remove edition qualifiers ("Nth Anniversary", "Special Edition", "Limited", "Reserve") and beer style suffixes (IPA, Stout, NE IPA, etc.). Example: "The Realm's Remedy 11th Anniversary IPA" → "The Realm's Remedy". "Casimiroa NE IPA" → "Casimiroa".
        - **search_hint**: A short, optimized Untappd search query (max ~4 words). Format: "[beer_name_core] [brewery_name_en]". If the brewery is Japanese and the official English name is uncertain, use the Japanese brewery name instead. Example: "Chakabuki Yamorido", "ROOTS ROCK Yorocco".
 
        Output JSON:
        {{
          "brewery_name_jp": "...", "brewery_name_en": "...",
          "beer_name_jp": "...", "beer_name_en": "...",
          "beer_name_core": "...",
          "search_hint": "...",
          "product_type": "...", "is_set": boolean
        }}
 
        Examples:
        {examples if examples else '''1. "Beer Name / Brewery" -> {{"brewery_name_en": "Brewery", "beer_name_en": "Beer Name", "beer_name_core": "Beer Name", "search_hint": "Beer Name Brewery", "product_type": "beer"}}
2. "【カシミロア/バテレ】(VERTERE Casimiroa NE IPA)" -> {{"brewery_name_jp": "バテレ", "brewery_name_en": "VERTERE", "beer_name_en": "Casimiroa NE IPA", "beer_name_core": "Casimiroa", "search_hint": "Casimiroa VERTERE", "product_type": "beer"}}
3. "【ROOTS ROCK/ヨロッコ】" -> {{"brewery_name_jp": "ヨロッコ", "brewery_name_en": "Yorocco Beer", "beer_name_en": "ROOTS ROCK", "beer_name_core": "ROOTS ROCK", "search_hint": "ROOTS ROCK Yorocco", "product_type": "beer"}}'''}
        """

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> GeminiExtraction:
        """Main entry point for extracting beer information."""
        if not self.client or self.daily_request_count >= self.global_daily_limit:
            return self._empty_result()

        logger.info(f"[Gemini] Extracting: {product_name} (Known: {known_brewery}, Shop: {shop})")

        hint: str = f"\nNote: The brewery exists and is likely: \"{known_brewery}\"" if known_brewery else ""
        guidance, examples = self._get_shop_guidance(shop)
        prompt: str = self._build_prompt(product_name, hint, guidance, examples)

        logger.debug(f"[Gemini] Full Prompt:\n{'-'*40}\n{prompt}\n{'-'*40}")

        try:
            data: Optional[Dict[str, Any]] = await self._generate_content(prompt)
            if data:
                logger.info(f"  ✅ Extraction Success:")
                logger.info(f"     - Brewery: {data.get('brewery_name_en')} ({data.get('brewery_name_jp')})")
                logger.info(f"     - Beer:    {data.get('beer_name_en')} ({data.get('beer_name_jp')})")
                logger.info(f"     - Type:    {data.get('product_type')} (Set: {data.get('is_set')})")
                
                logger.debug(f"[Gemini] Success. Daily usage: {self.daily_request_count}/{self.global_daily_limit}")
                res: GeminiExtraction = {
                    "brewery_name_jp": data.get("brewery_name_jp"),
                    "brewery_name_en": data.get("brewery_name_en"),
                    "beer_name_jp": data.get("beer_name_jp"),
                    "beer_name_en": data.get("beer_name_en"),
                    "beer_name_core": data.get("beer_name_core"),
                    "search_hint": data.get("search_hint"),
                    "product_type": data.get("product_type", "beer"),
                    "is_set": data.get("is_set", False),
                    "raw_response": data.get("raw_response")
                }
                return res
        except Exception as e:
            logger.error(f"[Gemini] Extraction failed: {e}")

        return self._empty_result()

    def _empty_result(self) -> GeminiExtraction:
        """Returns a default empty result structure."""
        return {
            "brewery_name_jp": None,
            "brewery_name_en": None,
            "beer_name_jp": None,
            "beer_name_en": None,
            "beer_name_core": None,
            "search_hint": None,
            "product_type": "beer",
            "is_set": False,
            "raw_response": None
        }

    async def suggest_search_queries(self, product_name: str, brewery: str, beer_name: str) -> List[str]:
        """
        Two-pass retry: When Untappd search fails, ask Gemini for alternative search queries.
        Returns a list of short search query strings to try.
        """
        if not self.client:
            return []

        prompt: str = f"""
        An Untappd search for a craft beer has failed. Suggest 3 short, alternative search queries to find it.
 
        Product Title: "{product_name}"
        Brewery: "{brewery}"
        Beer Name: "{beer_name}"
 
        Rules:
        - Each query should be short (2-5 words)
        - Try different combinations: core beer name, brewery abbreviation, key unique words
        - Remove edition qualifiers (Anniversary, Edition, Limited, etc.)
        - Remove beer style suffixes (IPA, Stout, Pale Ale, etc.) if the name has other unique words
        - The goal is to find the beer on Untappd.com
 
        Output JSON only:
        {{"queries": ["query1", "query2", "query3"]}}
        """

        try:
            data: Optional[Dict[str, Any]] = await self._generate_content(prompt)
            if data and isinstance(data.get("queries"), list):
                queries: List[str] = [q for q in data["queries"] if isinstance(q, str) and len(q) >= 3]
                logger.info(f"  [Gemini] Suggested retry queries: {queries}")
                return queries[:5]  # Max 5 queries
        except Exception as e:
            logger.error(f"[Gemini] suggest_search_queries failed: {e}")

        return []

# Usage Example:
# extractor = GeminiExtractor()
# info = await extractor.extract_info("West Coast IPA / Green Cheek Beer Co.")

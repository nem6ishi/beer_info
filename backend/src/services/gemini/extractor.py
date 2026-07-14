import os
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple, cast
from google import genai
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
from ...core.types import GeminiExtraction
from ...core.db import get_supabase_client
from .cache_resolver import LocalCacheResolver

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
        
        # Initialize Cache Resolver
        self.cache_resolver = LocalCacheResolver()
        
        # Rate Limiting Configuration
        self.last_request_time = 0
        self.daily_request_count = 0
        
        # Model Configuration: Gemma 4 31B (15 RPM, 1,500 RPD)
        self.model_id = os.getenv("GEMINI_MODEL_ID", "gemma-4-31b-it")
        self.fallback_model_id = os.getenv("GEMINI_FALLBACK_MODEL_ID", "gemma-4-26b-a4b-it")
        self.model_interval = 4.5  # 15 RPMの制限に余裕を持たせる (約 13.3 RPM)
        self.global_daily_limit = 1450  # 1,500 RPDの制限に余裕を持たせる

    def _supports_response_schema(self, model_id: str) -> bool:
        """Returns True if the model supports response_schema (e.g. Gemini models)."""
        return model_id.lower().startswith("gemini-")


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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
    async def _generate_content(self, prompt: str, schema: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Generates content using the configured model with fallback and optional schema."""
        if not self.client:
            return None

        try:
            try:
                supabase = get_supabase_client()
                # Atomically increment the usage counter for today
                res = supabase.rpc('increment_api_usage', {'p_service_name': 'gemini'}).execute()
                current_usage = res.data
                self.daily_request_count = current_usage
                
                if current_usage > self.global_daily_limit:
                    logger.warning(f"  [Gemini] Global daily limit reached ({current_usage}/{self.global_daily_limit}). Skipping extraction.")
                    return None
            except Exception as db_e:
                logger.error(f"  [Gemini] Failed to increment API usage in DB: {db_e}. Falling back to local limit.")
                self.daily_request_count += 1
                if self.daily_request_count > self.global_daily_limit:
                    logger.warning(f"  [Gemini] Local daily limit reached ({self.daily_request_count}/{self.global_daily_limit}). Skipping extraction.")
                    return None

            await self._throttle(self.model_interval, self.model_id)

            config = None
            if schema and self._supports_response_schema(self.model_id):
                from google.genai import types
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                )

            logger.info(f"  [Gemini] Calling {self.model_id}...")
            response: Any = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=config,
            )
        except Exception as e:
            error_msg: str = str(e).lower()
            if getattr(e, 'code', None) == 429 or "exhausted" in error_msg or "quota" in error_msg or "unavailable" in error_msg:
                if self.model_id != self.fallback_model_id:
                    logger.warning(f"  [Gemini] {self.model_id} limit reached or unavailable. Falling back to {self.fallback_model_id}")
                    self.model_id = self.fallback_model_id
                    await self._throttle(self.model_interval, self.model_id)
                    logger.info(f"  [Gemini] Calling fallback {self.model_id}...")
                    fallback_config = None
                    if schema and self._supports_response_schema(self.model_id):
                        from google.genai import types
                        fallback_config = types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=schema,
                        )
                    response = await self.client.aio.models.generate_content(
                        model=self.model_id,
                        contents=prompt,
                        config=fallback_config,
                    )
                else:
                    raise
            else:
                raise
        
        self.last_request_time = time.time()
        # daily_request_count is now updated before the request
        
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
        """Parses JSON from response text, cleaning markdown blocks and normalizing schema fields."""
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
                normalized: Dict[str, Any] = dict(data)  # Keep all keys from parsed JSON
                for key in ["brewery_name_jp", "brewery_name_en", "beer_name_jp", "beer_name_en", "beer_name_core", "search_hint", "english_brewery_name", "brewery_slug", "english_beer_name"]:
                    val = data.get(key)
                    normalized[key] = str(val).strip() if isinstance(val, str) and val.strip() else None
                
                ptype = data.get("product_type")
                normalized["product_type"] = ptype if ptype in ["beer", "set", "glass", "other"] else "beer"
                normalized["is_set"] = bool(data.get("is_set", False))
                
                if "queries" in data and isinstance(data["queries"], list):
                    normalized["queries"] = [str(q).strip() for q in data["queries"] if isinstance(q, str) and str(q).strip()]
                
                normalized["raw_response"] = text
                return normalized
            return None
        except Exception as e:
            logger.error(f"  [Gemini] Failed to parse JSON: {e}")
            return None

    def _get_shop_guidance(self, shop: Optional[str]) -> Tuple[str, str]:
        """Provides specific formatting rules and examples based on the shop."""
        guidance: str = ""
        examples: str = ""

        if shop and self.shop_rules:
            target: Optional[Dict[str, Any]] = self.shop_rules.get(shop)
            if not target:
                shop_lower = shop.lower()
                for k, v in self.shop_rules.items():
                    if k.lower() == shop_lower:
                        target = v
                        break
            if target:
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

    def _clean_product_title(self, title: str, shop: Optional[str]) -> str:
        """Removes common shop-specific noise from the title before sending to Gemini."""
        import re
        if not title:
            return ""
        
        # ちょうせいやは【ビール名/ブルワリー名】の形式のためスキップ
        if shop != "ちょうせいや":
            # 【】で囲まれた特定の注意事項（予定、ご注文、本以上、入荷、クール便、限定、予約、空輸など）を削除
            pattern = r'【[^】]*(?:予定|ご注文|本以上|入荷|クール便|限定|予約|空輸|おひとり様|必須|同時購入|推し)[^】]*】'
            title = re.sub(pattern, '', title)
        
        return title.strip()

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> GeminiExtraction:
        """Main entry point for extracting beer information."""
        # 1. Tier 1: Product Title Exact Match Cache
        tier1_res = await self.cache_resolver.resolve_tier1_exact_match(product_name)
        if tier1_res:
            return tier1_res

        # 2. Tier 2: Dictionary Match Cache
        tier2_res = await self.cache_resolver.resolve_tier2_dictionary_match(product_name, shop)
        if tier2_res:
            return tier2_res

        if not self.client or self.daily_request_count >= self.global_daily_limit:
            return self._empty_result()

        clean_name = self._clean_product_title(product_name, shop)
        logger.info(f"[Gemini] Extracting: {clean_name} (Original: {product_name}, Known: {known_brewery}, Shop: {shop})")

        hint: str = f"\nNote: The brewery exists and is likely: \"{known_brewery}\"" if known_brewery else ""
        guidance, examples = self._get_shop_guidance(shop)
        prompt: str = self._build_prompt(clean_name, hint, guidance, examples)

        logger.debug(f"[Gemini] Full Prompt:\n{'-'*40}\n{prompt}\n{'-'*40}")

        try:
            schema = None
            if self._supports_response_schema(self.model_id):
                from google.genai import types
                schema = types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "brewery_name_jp": types.Schema(type=types.Type.STRING, nullable=True),
                        "brewery_name_en": types.Schema(type=types.Type.STRING, nullable=True),
                        "beer_name_jp": types.Schema(type=types.Type.STRING, nullable=True),
                        "beer_name_en": types.Schema(type=types.Type.STRING, nullable=True),
                        "beer_name_core": types.Schema(type=types.Type.STRING, nullable=True),
                        "search_hint": types.Schema(type=types.Type.STRING, nullable=True),
                        "product_type": types.Schema(type=types.Type.STRING, enum=["beer", "set", "glass", "other"]),
                        "is_set": types.Schema(type=types.Type.BOOLEAN),
                    },
                    required=["product_type", "is_set"],
                )
            data: Optional[Dict[str, Any]] = await self._generate_content(prompt, schema=schema)
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
            schema = None
            if self._supports_response_schema(self.model_id):
                from google.genai import types
                schema = types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "queries": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING)
                        )
                    },
                    required=["queries"],
                )
            data: Optional[Dict[str, Any]] = await self._generate_content(prompt, schema=schema)
            if data and isinstance(data.get("queries"), list):
                queries: List[str] = [q for q in data["queries"] if isinstance(q, str) and len(q) >= 3]
                logger.info(f"  [Gemini] Suggested retry queries: {queries}")
                return queries[:5]  # Max 5 queries
        except Exception as e:
            logger.error(f"[Gemini] suggest_search_queries failed: {e}")

        return []

    async def infer_untappd_brewery_info(self, product_name: str, brewery: str, beer_name: str) -> Optional[Dict[str, str]]:
        """
        When an Untappd search hits no_results, infer the exact English brewery name,
        likely Untappd brewery URL slug, and English beer name from Japanese/Katakana input.
        """
        if not self.client:
            return None

        prompt: str = f"""
        An Untappd search for a craft beer failed because the Japanese/Katakana text does not match Untappd's English database.
        Please infer the exact official English brewery name, its likely URL slug on Untappd (e.g. 'finback-brewery' or 'ise-kado-brewery'), and the official English beer name.

        Product Title: "{product_name}"
        Brewery Text: "{brewery}"
        Beer Name Text: "{beer_name}"

        Rules:
        - Convert Katakana names to their official English names (e.g. 'フィンバック' -> 'Finback Brewery', 'アザーハーフ' -> 'Other Half Brewing Co.', '箕面ビール' -> 'Minoh Beer').
        - 'brewery_slug' must be lowercase with hyphens, matching standard Untappd slug conventions (e.g. 'other-half-brewing-co', 'minoh-beer').
        - 'english_beer_name' should remove Japanese edition tags and style suffixes if redundant, giving the clean core English name on Untappd.

        Output JSON only:
        {{
            "english_brewery_name": "...",
            "brewery_slug": "...",
            "english_beer_name": "..."
        }}
        """

        try:
            schema = None
            if self._supports_response_schema(self.model_id):
                from google.genai import types
                schema = types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "english_brewery_name": types.Schema(type=types.Type.STRING),
                        "brewery_slug": types.Schema(type=types.Type.STRING),
                        "english_beer_name": types.Schema(type=types.Type.STRING)
                    },
                    required=["english_brewery_name", "brewery_slug", "english_beer_name"],
                )
            data: Optional[Dict[str, Any]] = await self._generate_content(prompt, schema=schema)
            if data and isinstance(data, dict):
                eb = data.get("english_brewery_name")
                bs = data.get("brewery_slug")
                en = data.get("english_beer_name")
                if eb and bs and en:
                    logger.info(f"  🤖 [Gemini Inference] Brewery: '{eb}' (slug: {bs}), Beer: '{en}'")
                    return {
                        "english_brewery_name": str(eb).strip(),
                        "brewery_slug": str(bs).strip().lower(),
                        "english_beer_name": str(en).strip()
                    }
        except Exception as e:
            logger.error(f"[Gemini] infer_untappd_brewery_info failed: {e}")

        return None

    async def select_best_untappd_candidate(
        self,
        product_name: str,
        brewery: str,
        beer_name: str,
        candidates: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Selects the best matching Untappd candidate from a Top-N search candidate list using LLM reasoning.
        Returns the chosen candidate dict (with 'selection_reason' added), or None if no candidate matches accurately.
        """
        if not self.client or not candidates:
            return None

        candidates_str_list = []
        for idx, c in enumerate(candidates):
            b_name = c.get('beer_name', 'Unknown Beer')
            br_name = c.get('brewery_name', 'Unknown Brewery')
            st_name = c.get('style', '')
            url = c.get('url', '')
            candidates_str_list.append(f"[{idx}] Beer: \"{b_name}\" | Brewery: \"{br_name}\" | Style: \"{st_name}\" | URL: {url}")
        candidates_text = "\n".join(candidates_str_list)

        prompt: str = f"""
        We searched Untappd for a craft beer but got multiple candidate results.
        Please choose the single best matching candidate from the list below, or return -1 if none of them accurately match the target product.

        Target Product Info:
        - Product Title: "{product_name}"
        - Expected Brewery: "{brewery}"
        - Expected Beer Name: "{beer_name}"

        Candidate Results from Untappd:
{candidates_text}

        Rules:
        1. **Strict Variant Matching**: If the target product specifies a specific variant or edition (e.g., DDH, Double Dry Hopped, Barrel Aged / BA, TIPA, Hazy, Specific Vintage Year like 2023 or 2024), the selected candidate MUST exactly match that variant or vintage. Do not pick the regular version or a different vintage year if the specific one is requested. If the requested exact variant/vintage is NOT in the candidate list, return -1 (no match).
        2. **Collab Matching**: If the target is a collaboration beer (e.g., A x B), candidate names might list the breweries in a different order (e.g., B / A) or include both names. This is a valid match.
        3. **Japanese to English Mapping**: The target product info may be in Japanese or Katakana. Match them correctly to their English/Romanized equivalents on Untappd.
        4. **No Match Option**: If none of the candidates accurately represent the target product, you MUST output selected_index as -1. Do not guess or force a wrong match.

        Output JSON only:
        {{
            "selected_index": 0,
            "reason": "Clear brief explanation for why this candidate was selected or why none matched."
        }}
        """

        try:
            schema = None
            if self._supports_response_schema(self.model_id):
                from google.genai import types
                schema = types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "selected_index": types.Schema(type=types.Type.INTEGER),
                        "reason": types.Schema(type=types.Type.STRING)
                    },
                    required=["selected_index", "reason"],
                )
            data: Optional[Dict[str, Any]] = await self._generate_content(prompt, schema=schema)
            if data and isinstance(data, dict):
                idx = int(data.get("selected_index", -1))
                reason = str(data.get("reason", ""))
                logger.info(f"  🤖 [LLM Selection] Selected index: {idx} | Reason: {reason}")
                if 0 <= idx < len(candidates):
                    chosen = dict(candidates[idx])
                    chosen['selection_reason'] = reason
                    return chosen
                else:
                    logger.info("  🤖 [LLM Selection] LLM judged NO MATCH (-1) among candidates.")
                    return None
        except Exception as e:
            logger.error(f"[Gemini] select_best_untappd_candidate failed: {e}")

        return None

# Usage Example:
# extractor = GeminiExtractor()
# info = await extractor.extract_info("West Coast IPA / Green Cheek Beer Co.")


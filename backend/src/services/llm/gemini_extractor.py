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
from .base import BaseExtractor
from .prompt_builder import PromptBuilder

load_dotenv()

logger = logging.getLogger(__name__)

class GeminiExtractor(BaseExtractor):
    client: Optional[genai.Client]
    prompt_builder: PromptBuilder
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
        
        self.prompt_builder = PromptBuilder()
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


    def _supports_response_schema(self, model_id: str) -> bool:
        """Returns True if the model supports response_schema (e.g. Gemini models)."""
        return model_id.lower().startswith("gemini-")

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
            # 意図: 無料枠のGemini APIはレートリミット(429)やリソース枯渇(unavailable)が起きやすいため、
            # エラーを検知したら、別のモデル（fallback_model_id）に切り替えて即座にリトライを行う。
            # fallback_model_id はレートリミットの枠が別であるため成功しやすい。
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
            # 意図: LLM（特にGemini以外のローカルモデル等）は system prompt で JSON出力 を指定しても、
            # ```json ... ``` のようなマークダウンブロックで囲って返してくることがあるため、
            # json.loads がパースエラーを起こさないように前後のマークダウン記法をサニタイズ（除去）する。
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

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> GeminiExtraction:
        """Main entry point for extracting beer information."""
        # 1. Tier 1: Product Title Exact Match Cache
        tier1_res = await self.cache_resolver.resolve_tier1_exact_match(product_name)
        if tier1_res:
            return self.prompt_builder.apply_set_override(tier1_res, product_name)

        # 2. Tier 2: Dictionary Match Cache
        tier2_res = await self.cache_resolver.resolve_tier2_dictionary_match(product_name, shop)
        if tier2_res:
            return self.prompt_builder.apply_set_override(tier2_res, product_name)

        if not self.client or self.daily_request_count >= self.global_daily_limit:
            return self.prompt_builder.apply_set_override(self.prompt_builder.empty_result(), product_name)

        clean_name = self.prompt_builder.clean_product_title(product_name, shop)
        logger.info(f"[Gemini] Extracting: {clean_name} (Original: {product_name}, Known: {known_brewery}, Shop: {shop})")

        prompt: str = self.prompt_builder.build_extract_prompt(product_name, known_brewery, shop)

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
                return self.prompt_builder.apply_set_override(res, product_name)
        except Exception as e:
            logger.error(f"[Gemini] Extraction failed: {e}")

        return self.prompt_builder.apply_set_override(self.prompt_builder.empty_result(), product_name)

    async def suggest_search_queries(self, product_name: str, brewery: str, beer_name: str) -> List[str]:
        """
        Two-pass retry: When Untappd search fails, ask Gemini for alternative search queries.
        Returns a list of short search query strings to try.
        """
        if not self.client:
            return []

        prompt: str = self.prompt_builder.build_suggest_search_queries_prompt(product_name, brewery, beer_name)

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

        prompt: str = self.prompt_builder.build_infer_untappd_brewery_info_prompt(product_name, brewery, beer_name)

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

        prompt: str = self.prompt_builder.build_select_best_candidate_prompt(product_name, brewery, beer_name, candidates)

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


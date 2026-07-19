import os
import json
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv

from .base import BaseExtractor
from ...core.types import GeminiExtraction
from .gemini_extractor import GeminiExtractor  # For reusing common prompt building for now

load_dotenv()
logger = logging.getLogger(__name__)

class LocalMlxExtractor(BaseExtractor):
    def __init__(self, model_id: Optional[str] = None) -> None:
        self.model_id = model_id or os.getenv("LOCAL_LLM_MODEL_ID", "prism-ml/Ternary-Bonsai-27B-mlx-2bit")
        self.model = None
        self.tokenizer = None
        # Reusing GeminiExtractor's prompt building and rule loading for compatibility
        self._prompt_helper = GeminiExtractor()

    def _load_model(self):
        if self.model is None or self.tokenizer is None:
            try:
                from mlx_lm import load
                logger.info(f"🌿 Loading Local MLX model [{self.model_id}]...")
                self.model, self.tokenizer = load(self.model_id)
                logger.info("✅ Model loaded successfully.")
            except ImportError:
                logger.error("❌ mlx_lm is not installed. Cannot use LocalMlxExtractor.")
                raise
            except Exception as e:
                logger.error(f"❌ Failed to load local model: {e}")
                raise

    def _safe_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        content = text.strip()
        candidates = []
        start_pos = 0
        while True:
            s = content.find("{", start_pos)
            if s == -1:
                break
            e = content.rfind("}") + 1
            while e > s:
                candidate_str = content[s:e]
                try:
                    data = json.loads(candidate_str)
                    if isinstance(data, dict):
                        candidates.append((len(candidate_str), data))
                        break
                except Exception:
                    pass
                e = content.rfind("}", s, e - 1) + 1
            start_pos = s + 1

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        return None

    async def _generate_local(self, prompt: str) -> Tuple[Optional[Dict[str, Any]], float]:
        self._load_model()
        from mlx_lm import stream_generate
        
        messages = [{"role": "user", "content": prompt}]
        if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
            chat_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            chat_prompt = f"User: {prompt}\nAssistant:\n"
        
        json_prefix = "```json\n{\n"
        chat_prompt += json_prefix
        
        start_time = time.perf_counter()
        generated_text = "{\n"
        try:
            # Using synchronous stream_generate in a thread to avoid blocking the event loop
            def run_inference():
                res_text = "{\n"
                for response in stream_generate(self.model, self.tokenizer, chat_prompt, max_tokens=1500):
                    token_str = response.text
                    res_text += token_str
                    if "```" in token_str or "<|im_end|>" in token_str or "<|channel>" in token_str:
                        break
                    if "}" in res_text:
                        test_str = res_text.split("```")[0].split("<|im_end|>")[0].strip()
                        try:
                            data = json.loads(test_str)
                            if isinstance(data, dict):
                                break
                        except Exception:
                            pass
                return res_text

            # Run in executor to not block asyncio
            loop = asyncio.get_running_loop()
            generated_text = await loop.run_in_executor(None, run_inference)
            
            elapsed = time.perf_counter() - start_time
            data = self._safe_parse_json(generated_text)
            return data, elapsed
        except Exception as e:
            logger.warning(f"  ❌ [LocalMlx] Inference error: {e}")
            return None, time.perf_counter() - start_time

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> GeminiExtraction:
        clean_name = self._prompt_helper._clean_product_title(product_name, shop)
        hint: str = f"Note: The brewery exists and is likely: '{known_brewery}'" if known_brewery else ""
        guidance, examples = self._prompt_helper._get_shop_guidance(shop)
        prompt: str = self._prompt_helper._build_prompt(clean_name, hint, guidance, examples)

        data, elapsed = await self._generate_local(prompt)
        
        if not data:
            return self._prompt_helper._apply_set_override(self._prompt_helper._empty_result(), product_name)

        res: GeminiExtraction = {
            "brewery_name_jp": data.get("brewery_name_jp"),
            "brewery_name_en": data.get("brewery_name_en"),
            "beer_name_jp": data.get("beer_name_jp"),
            "beer_name_en": data.get("beer_name_en"),
            "beer_name_core": data.get("beer_name_core"),
            "search_hint": data.get("search_hint"),
            "product_type": data.get("product_type", "beer"),
            "is_set": data.get("is_set", False),
            "raw_response": json.dumps(data, ensure_ascii=False)
        }
        return self._prompt_helper._apply_set_override(res, product_name)

    async def suggest_search_queries(self, product_name: str, brewery: str, beer_name: str) -> List[str]:
        prompt: str = f"""
        An Untappd search for a craft beer has failed. Suggest 3 short, alternative search queries to find it.
        Product Title: "{product_name}"
        Brewery: "{brewery}"
        Beer Name: "{beer_name}"
        Rules:
        - Each query should be short (2-5 words)
        - Try different combinations: core beer name, brewery abbreviation, key unique words
        Output JSON only:
        {{"queries": ["query1", "query2", "query3"]}}
        """
        data, _ = await self._generate_local(prompt)
        if data and isinstance(data.get("queries"), list):
            return [str(q) for q in data["queries"] if str(q).strip()][:5]
        return []

    async def infer_untappd_brewery_info(self, product_name: str, brewery: str, beer_name: str) -> Optional[Dict[str, str]]:
        prompt: str = f"""
        An Untappd search for a craft beer failed because the Japanese/Katakana text does not match Untappd's English database.
        Please infer the exact official English brewery name, its likely URL slug on Untappd (e.g. 'finback-brewery' or 'ise-kado-brewery'), and the official English beer name.
        Product Title: "{product_name}"
        Brewery Text: "{brewery}"
        Beer Name Text: "{beer_name}"
        Rules:
        - Convert Katakana names to their official English names.
        Output JSON only:
        {{
            "english_brewery_name": "...",
            "brewery_slug": "...",
            "english_beer_name": "..."
        }}
        """
        data, _ = await self._generate_local(prompt)
        if data and data.get("english_brewery_name"):
            return {
                "english_brewery_name": str(data.get("english_brewery_name", "")).strip(),
                "brewery_slug": str(data.get("brewery_slug", "")).strip().lower(),
                "english_beer_name": str(data.get("english_beer_name", "")).strip()
            }
        return None

    async def select_best_untappd_candidate(self, product_name: str, brewery: str, beer_name: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # Omitted for brevity, but implement basic proxy to local LLM similar to GeminiExtractor
        if not candidates: return None
        candidates_str_list = []
        for idx, c in enumerate(candidates):
            candidates_str_list.append(f"[{idx}] Beer: '{c.get('beer_name')}' | Brewery: '{c.get('brewery_name')}'")
        candidates_text = "\\n".join(candidates_str_list)

        prompt: str = f"""
        We searched Untappd for a craft beer but got multiple candidate results.
        Please choose the single best matching candidate from the list below, or return -1 if none match.
        Target Product: "{product_name}" (Brewery: "{brewery}", Beer: "{beer_name}")
        Candidates:
{candidates_text}
        Output JSON only:
        {{
            "selected_index": 0,
            "reason": "..."
        }}
        """
        data, _ = await self._generate_local(prompt)
        if data:
            idx = int(data.get("selected_index", -1))
            if 0 <= idx < len(candidates):
                chosen = dict(candidates[idx])
                chosen['selection_reason'] = str(data.get("reason", ""))
                return chosen
        return None

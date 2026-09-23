import os
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv

# XetHubクライアントのハングバグを防止するため無効化
os.environ["HF_HUB_DISABLE_XET"] = "1"

from .base import BaseExtractor
from .prompt_builder import PromptBuilder
from ...core.types import GeminiExtraction

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "prism-ml/Ternary-Bonsai-2-27B-mlx-2bit"

class LocalMlxExtractor(BaseExtractor):
    def __init__(self, model_id: Optional[str] = None) -> None:
        self.model_id = model_id or os.getenv("LOCAL_LLM_MODEL_ID", DEFAULT_MODEL_ID)
        self.model = None
        self.tokenizer = None
        self.processor = None
        self.config = None
        self.chat_config = None
        self.is_bonsai2 = False
        self.prompt_builder = PromptBuilder()

    def _load_model(self):
        if self.model is not None:
            return

        is_b2 = "Ternary-Bonsai-2" in self.model_id or "bonsai-2" in self.model_id.lower()

        if is_b2:
            try:
                from huggingface_hub import snapshot_download
                logger.info(f"🌿 Loading Bonsai 2 Local MLX model [{self.model_id}] via custom runtime...")
                model_dir = snapshot_download(
                    repo_id=self.model_id,
                    allow_patterns=["*.json", "*.safetensors", "*.jinja", "runtime/*", "README.md", "PACK-RUNTIME.md"]
                )

                runtime_dir = Path(model_dir) / "runtime"
                import sys
                if str(runtime_dir) not in sys.path:
                    sys.path.insert(0, str(runtime_dir))

                from vision_artifact import load_vl_model, chat_config
                self.model, self.processor, self.config = load_vl_model(model_dir)
                self.chat_config = chat_config(self.config)
                self.is_bonsai2 = True
                logger.info("✅ Bonsai 2 model loaded successfully.")
                return
            except Exception as e:
                logger.error(f"❌ Failed to load Bonsai 2 model: {e}")
                raise
        else:
            try:
                from mlx_lm import load
                logger.info(f"🌿 Loading Local MLX model [{self.model_id}]...")
                self.model, self.tokenizer = load(self.model_id)
                self.is_bonsai2 = False
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
        start_time = time.perf_counter()

        if self.is_bonsai2:
            from mlx_vlm import generate
            from mlx_vlm.prompt_utils import apply_chat_template

            formatted_prompt = apply_chat_template(
                self.processor,
                self.chat_config,
                prompt,
                num_images=0
            )
            json_prefix = "```json\n{\n"
            formatted_prompt += json_prefix

            def run_bonsai2_inference():
                gen_result = generate(
                    model=self.model,
                    processor=self.processor,
                    prompt=formatted_prompt,
                    max_tokens=1000,
                    temperature=0.7,
                    verbose=False
                )
                output_text = gen_result.text if hasattr(gen_result, "text") else str(gen_result)
                return "{\n" + output_text.split("```")[0].strip()

            try:
                loop = asyncio.get_running_loop()
                generated_text = await loop.run_in_executor(None, run_bonsai2_inference)
                elapsed = time.perf_counter() - start_time
                data = self._safe_parse_json(generated_text)
                return data, elapsed
            except Exception as e:
                logger.warning(f"  ❌ [LocalMlx-Bonsai2] Inference error: {e}")
                return None, time.perf_counter() - start_time

        else:
            from mlx_lm import stream_generate

            messages = [{"role": "user", "content": prompt}]
            if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template:
                chat_prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            else:
                chat_prompt = f"User: {prompt}\nAssistant:\n"

            json_prefix = "```json\n{\n"
            chat_prompt += json_prefix

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

            try:
                loop = asyncio.get_running_loop()
                generated_text = await loop.run_in_executor(None, run_inference)
                elapsed = time.perf_counter() - start_time
                data = self._safe_parse_json(generated_text)
                return data, elapsed
            except Exception as e:
                logger.warning(f"  ❌ [LocalMlx] Inference error: {e}")
                return None, time.perf_counter() - start_time

    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> GeminiExtraction:
        prompt: str = self.prompt_builder.build_extract_prompt(product_name, known_brewery, shop)
        data, elapsed = await self._generate_local(prompt)

        if not data:
            return self.prompt_builder.apply_set_override(self.prompt_builder.empty_result(), product_name)

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
        return self.prompt_builder.apply_set_override(res, product_name)

    async def suggest_search_queries(self, product_name: str, brewery: str, beer_name: str) -> List[str]:
        prompt: str = self.prompt_builder.build_suggest_search_queries_prompt(product_name, brewery, beer_name)
        data, _ = await self._generate_local(prompt)
        if data and isinstance(data.get("queries"), list):
            return [str(q) for q in data["queries"] if str(q).strip()][:5]
        return []

    async def infer_untappd_brewery_info(self, product_name: str, brewery: str, beer_name: str) -> Optional[Dict[str, str]]:
        prompt: str = self.prompt_builder.build_infer_untappd_brewery_info_prompt(product_name, brewery, beer_name)
        data, _ = await self._generate_local(prompt)
        if data and data.get("english_brewery_name"):
            return {
                "english_brewery_name": str(data.get("english_brewery_name", "")).strip(),
                "brewery_slug": str(data.get("brewery_slug", "")).strip().lower(),
                "english_beer_name": str(data.get("english_beer_name", "")).strip()
            }
        return None

    async def select_best_untappd_candidate(self, product_name: str, brewery: str, beer_name: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not candidates: return None
        prompt: str = self.prompt_builder.build_select_best_candidate_prompt(product_name, brewery, beer_name, candidates)
        data, _ = await self._generate_local(prompt)
        if data:
            idx = int(data.get("selected_index", -1))
            if 0 <= idx < len(candidates):
                chosen = dict(candidates[idx])
                chosen['selection_reason'] = str(data.get("reason", ""))
                return chosen
        return None

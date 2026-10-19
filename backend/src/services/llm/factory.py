from typing import Optional
from .base import BaseExtractor

_gemini_instance: Optional[BaseExtractor] = None

def get_llm_extractor(provider: str = "gemini", model_id: Optional[str] = None) -> BaseExtractor:
    """
    Factory function to get the appropriate LLM Extractor.
    provider: 'gemini' or 'local_mlx'
    """
    global _gemini_instance
    if provider == "local_mlx":
        from .local_mlx_extractor import LocalMlxExtractor
        return LocalMlxExtractor(model_id=model_id)
    else:
        # Default to gemini (singleton to preserve rate limit timers, cooldowns, and brewery dictionary cache)
        if _gemini_instance is None:
            from .gemini_extractor import GeminiExtractor
            _gemini_instance = GeminiExtractor()
        return _gemini_instance


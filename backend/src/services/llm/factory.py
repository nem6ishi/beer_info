from typing import Optional
from .base import BaseExtractor

def get_llm_extractor(provider: str = "gemini", model_id: Optional[str] = None) -> BaseExtractor:
    """
    Factory function to get the appropriate LLM Extractor.
    provider: 'gemini' or 'local_mlx'
    """
    if provider == "local_mlx":
        from .local_mlx_extractor import LocalMlxExtractor
        return LocalMlxExtractor(model_id=model_id)
    else:
        # Default to gemini
        from .gemini_extractor import GeminiExtractor
        return GeminiExtractor()

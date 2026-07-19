from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from ...core.types import GeminiExtraction

class BaseExtractor(ABC):
    """
    Abstract base class for LLM Extractors (Gemini, Local MLX, etc.)
    """

    @abstractmethod
    async def extract_info(self, product_name: str, known_brewery: Optional[str] = None, shop: Optional[str] = None) -> GeminiExtraction:
        """
        Extracts brewery and beer names from the product title.
        """
        pass

    @abstractmethod
    async def suggest_search_queries(self, product_name: str, brewery: str, beer_name: str) -> List[str]:
        """
        Suggests alternative search queries to find a beer on Untappd.
        """
        pass

    @abstractmethod
    async def infer_untappd_brewery_info(self, product_name: str, brewery: str, beer_name: str) -> Optional[Dict[str, str]]:
        """
        Infers the exact official English brewery name, likely Untappd brewery URL slug, and English beer name.
        """
        pass

    @abstractmethod
    async def select_best_untappd_candidate(self, product_name: str, brewery: str, beer_name: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Selects the best matching Untappd candidate from a list of candidates.
        """
        pass

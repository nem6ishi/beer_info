import os
import logging
from typing import Optional, Dict, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMValidationResult(BaseModel):
    is_match: bool = Field(
        description="True if original_title and Untappd details refer to the exact same craft beer product, False otherwise."
    )
    confidence: float = Field(
        description="Confidence score of the judgment between 0.0 and 1.0."
    )
    reason: str = Field(
        description="Brief clear reason explaining why they match or do not match."
    )

class LLMValidator:
    """
    LLM-based validator to verify if a shop product title matches Untappd beer information.
    Uses Gemini API structured output without relying on hardcoded alias dictionaries.
    """
    
    def __init__(self, api_key: Optional[str] = None, model_id: Optional[str] = None) -> None:
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            logger.warning("[LLMValidator] GEMINI_API_KEY not found. LLM Validation will fallback to rule-based.")
            self.client = None
        else:
            self.client = genai.Client(api_key=key)
            
        self.model_id = model_id or os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash")
        self._cache: Dict[str, Tuple[bool, float, str]] = {}

    def validate_pair(
        self,
        original_title: str,
        untappd_brewery: str,
        untappd_beer: str,
        untappd_style: Optional[str] = None,
    ) -> Tuple[bool, float, str]:
        """
        Validates if original_title and Untappd info refer to the same craft beer.
        
        Returns:
            Tuple[is_match (bool), confidence (float), reason (str)]
        """
        if not original_title or not untappd_brewery or not untappd_beer:
            return False, 0.0, "Missing required input fields"

        cache_key = f"{original_title.strip()}|{untappd_brewery.strip()}|{untappd_beer.strip()}|{(untappd_style or '').strip()}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.client:
            # Fallback when API key is missing: basic string inclusion check
            orig_lower = original_title.lower()
            brew_lower = untappd_brewery.lower()
            beer_lower = untappd_beer.lower()
            
            # Simple fallback check
            brew_match = brew_lower in orig_lower or any(w in orig_lower for w in brew_lower.split() if len(w) >= 4)
            beer_match = beer_lower in orig_lower or any(w in orig_lower for w in beer_lower.split() if len(w) >= 4)
            is_match = brew_match and beer_match
            reason = "Fallback string check (No Gemini client)" if is_match else "Fallback check failed"
            result = (is_match, 0.7 if is_match else 0.0, reason)
            self._cache[cache_key] = result
            return result

        prompt = f"""You are an expert craft beer validator.
Determine if the scraped online shop product title and the Untappd search result refer to the SAME craft beer product.

Input Data:
- Original Shop Product Title: "{original_title}"
- Untappd Brewery Name: "{untappd_brewery}"
- Untappd Beer Name: "{untappd_beer}"
- Untappd Style: "{untappd_style or 'N/A'}"

Validation Rules:
1. BREWERY CHECK: Does the brewery in the original title match the Untappd brewery? (Japanese/English variants like 'うちゅうブルーイング' and 'Uchu Brewing' match, but DIFFERENT breweries like 'Uchu Brewing' and 'West Coast Brewing' MUST BE MARKED is_match = false).
2. BEER NAME CHECK: Does the beer name match (ignoring volume like 350ml, 473ml, can/bottle)?
3. PRODUCT TYPE CHECK: Are both craft beer products (not cider, cocktail, or glassware)?

Evaluate strictly and return JSON with is_match, confidence, and reason.
"""

        try:
            # Call Gemini API with Pydantic structured response
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LLMValidationResult,
                    temperature=0.1,
                ),
            )
            
            if response and response.parsed:
                parsed: LLMValidationResult = response.parsed
                res_tuple = (parsed.is_match, parsed.confidence, parsed.reason)
                logger.info(
                    f"  🤖 [LLMValidator] Pair Validation: is_match={parsed.is_match} (conf={parsed.confidence:.2f}) | '{original_title}' <-> Untappd '{untappd_brewery} / {untappd_beer}' | Reason: {parsed.reason}"
                )
                self._cache[cache_key] = res_tuple
                return res_tuple

        except Exception as e:
            logger.warning(f"[LLMValidator] API call error for '{original_title}': {e}")
            
        # Fallback in case of API failure
        fallback_res = (False, 0.0, "API Error during LLM validation")
        self._cache[cache_key] = fallback_res
        return fallback_res

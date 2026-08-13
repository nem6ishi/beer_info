import pytest
from unittest.mock import patch, MagicMock
from backend.src.services.llm.llm_validator import LLMValidator, LLMValidationResult
from backend.src.services.untappd.validators import validate_final_match

def test_llm_validator_match():
    validator = LLMValidator(api_key="mock_key")
    validator.client = MagicMock()
    
    mock_response = MagicMock()
    mock_response.parsed = LLMValidationResult(
        is_match=True,
        confidence=0.98,
        reason="Both refer to Uchu Brewing's Uchu Lager."
    )
    validator.client.models.generate_content.return_value = mock_response

    is_match, conf, reason = validator.validate_pair(
        original_title="うちゅうブルーイング / 宇宙LAGER (Helles) 350ml缶 [UCHU BREWING / UCHU LAGER]",
        untappd_brewery="Uchu Brewing",
        untappd_beer="宇宙LAGER (UCHU LAGER)",
        untappd_style="Lager - Helles"
    )

    assert is_match is True
    assert conf == 0.98
    assert "Uchu Brewing" in reason

def test_llm_validator_mismatch():
    validator = LLMValidator(api_key="mock_key")
    validator.client = MagicMock()
    
    mock_response = MagicMock()
    mock_response.parsed = LLMValidationResult(
        is_match=False,
        confidence=0.99,
        reason="Different breweries: Uchu Brewing in title vs West Coast Brewing in Untappd."
    )
    validator.client.models.generate_content.return_value = mock_response

    is_match, conf, reason = validator.validate_pair(
        original_title="うちゅうブルーイング / 宇宙LAGER (Helles) 350ml缶 [UCHU BREWING / UCHU LAGER]",
        untappd_brewery="West Coast Brewing",
        untappd_beer="Helles",
        untappd_style="Lager - Helles"
    )

    assert is_match is False
    assert conf == 0.99
    assert "Different breweries" in reason

@patch("backend.src.services.untappd.validators._get_llm_validator")
def test_validate_final_match_with_llm(mock_get_validator):
    mock_validator = MagicMock()
    mock_validator.client = MagicMock()
    mock_get_validator.return_value = mock_validator

    # Case 1: Mismatch blocked by LLM
    mock_validator.validate_pair.return_value = (False, 0.95, "Different brewery")
    res_bad = validate_final_match(
        original_title="うちゅうブルーイング / 宇宙LAGER (Helles) 350ml缶 [UCHU BREWING / UCHU LAGER]",
        untappd_beer_name="Helles",
        untappd_brewery_name="West Coast Brewing",
        untappd_style="Lager - Helles"
    )
    assert res_bad is False

    # Case 2: Match passed by LLM
    mock_validator.validate_pair.return_value = (True, 0.98, "Match confirmed")
    res_good = validate_final_match(
        original_title="うちゅうブルーイング / 宇宙LAGER (Helles) 350ml缶 [UCHU BREWING / UCHU LAGER]",
        untappd_beer_name="宇宙LAGER (UCHU LAGER)",
        untappd_brewery_name="Uchu Brewing",
        untappd_style="Lager - Helles"
    )
    assert res_good is True

import pytest
from unittest.mock import patch, MagicMock
from backend.src.services.untappd.validators import validate_final_match, validate_brewery_match

@pytest.fixture(autouse=True)
def mock_no_llm_validator():
    """By default, mock _get_llm_validator to return None so tests verify deterministically via rule-based guards."""
    with patch("backend.src.services.untappd.validators._get_llm_validator", return_value=None):
        yield


def test_validate_brewery_match_rio_cocktail_prevention():
    # RIO BREWING should NOT match Rio Cocktail
    res = validate_brewery_match({"brewery_name": "Rio Cocktail"}, "RIO BREWING")
    assert res is False, "Rio Cocktail should be rejected when looking for RIO BREWING"

    # RIO BREWING should match Rio Brewing & Co.
    res_valid = validate_brewery_match({"brewery_name": "Rio Brewing & Co."}, "RIO BREWING")
    assert res_valid is True, "Rio Brewing & Co. should be accepted for RIO BREWING"

def test_validate_final_match_tipsy():
    # Final match for TIPSY / RIO BREWING against Rio Cocktail -> False
    bad_match = validate_final_match(
        original_title="【TIPSY/RIO BREWING】",
        untappd_beer_name="Rio Tipsy Jelly Cocktail Osmanthus Green Plum",
        untappd_brewery_name="Rio Cocktail",
        untappd_style="RTD - Other",
        expected_brewery="RIO BREWING"
    )
    assert bad_match is False, "Final validation must block Rio Cocktail for TIPSY / RIO BREWING"

    # Final match for TIPSY / RIO BREWING against Rio Brewing & Co. -> True
    good_match = validate_final_match(
        original_title="【TIPSY/RIO BREWING】",
        untappd_beer_name="Tipsy",
        untappd_brewery_name="Rio Brewing & Co.",
        untappd_style="IPA - New England / Hazy",
        expected_brewery="RIO BREWING"
    )
    assert good_match is True, "Final validation must accept Rio Brewing & Co. Tipsy"

def test_validate_final_match_vintage_mismatch():
    # Title has no vintage -> Untappd has 2023BY -> Should be BLOCKED
    blocked = validate_final_match(
        original_title="【ENGI!? Sake IPA/志賀高原】",
        untappd_beer_name="Shiga Kogen Engi!? (2023BY)",
        untappd_brewery_name="Tamamura Honten Co.",
        untappd_style="Koji / Ginjo Beer",
        expected_brewery="Tamamura Honten Co."
    )
    assert blocked is False, "Final validation must block 2023BY vintage when title has no vintage"

    # Title explicitly has 2023BY -> Untappd has 2023BY -> Should be PASSED
    passed = validate_final_match(
        original_title="【ENGI!? Sake IPA 2023BY/志賀高原】",
        untappd_beer_name="Shiga Kogen Engi!? (2023BY)",
        untappd_brewery_name="Tamamura Honten Co.",
        untappd_style="Koji / Ginjo Beer",
        expected_brewery="Tamamura Honten Co."
    )
    assert passed is True, "Final validation must pass 2023BY vintage when title explicitly specifies 2023BY"

def test_validate_final_match_real_ale_mismatch():
    # Title has no Real Ale -> Untappd has Hansharo Real Soun -> Should be BLOCKED
    blocked1 = validate_final_match(
        original_title="【早雲/反射炉ビヤ】",
        untappd_beer_name="Hansharo Real Soun",
        untappd_brewery_name="Kuraya Narusawa | Hansharo Beer",
        untappd_style="Traditional Ale",
        expected_brewery="Hansharo Beer"
    )
    assert blocked1 is False, "Final validation must block Hansharo Real Soun when title does not specify Real Ale"

    # Title specifies NITRO -> Untappd has Real Ale Ver. -> Should be BLOCKED
    blocked2 = validate_final_match(
        original_title="【頼朝(NITRO)/反射炉ビヤ】",
        untappd_beer_name="Hansharo Yoritomo Real Ale Ver.",
        untappd_brewery_name="Kuraya Narusawa | Hansharo Beer",
        untappd_style="Porter - Other",
        expected_brewery="Hansharo Beer"
    )
    assert blocked2 is False, "Final validation must block Real Ale Ver. for NITRO product"


def test_validate_final_match_with_llm_validator():
    mock_validator = MagicMock()
    mock_validator.client = MagicMock()
    mock_validator.validate_pair.return_value = (False, 0.9, "LLM mismatched product")

    with patch("backend.src.services.untappd.validators._get_llm_validator", return_value=mock_validator):
        res = validate_final_match(
            original_title="【Some Beer/Brewery】",
            untappd_beer_name="Other Beer",
            untappd_brewery_name="Other Brewery"
        )
        assert res is False
        mock_validator.validate_pair.assert_called_once()


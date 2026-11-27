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


def test_validate_final_match_hard_seltzer_and_rtd():
    # English "Hard Seltzer" in title should be accepted for Hard Seltzer Untappd style
    passed_seltzer = validate_final_match(
        original_title="New Motion Cantina Picante Spicy Margarita Hard Seltzer (355ml)",
        untappd_beer_name="Cantina Picante",
        untappd_brewery_name="New Motion Beverages",
        untappd_style="Hard Seltzer",
        expected_brewery="New Motion"
    )
    assert passed_seltzer is True, "English Hard Seltzer title should match Hard Seltzer style"

    # Mojito / Punch RTD should also be accepted when title mentions mojito/punch
    passed_mojito = validate_final_match(
        original_title="Denver Watermelon Yuzu Mojito (355ml)",
        untappd_beer_name="Watermelon Yuzu Mojito",
        untappd_brewery_name="Denver Beer Co.",
        untappd_style="RTD - Cocktail",
        expected_brewery="Denver Beer Co."
    )
    assert passed_mojito is True, "Mojito title should match RTD - Cocktail style"

    # Spiked Seltzer (Upslope Spiked Snow Melt) should be accepted
    passed_spiked = validate_final_match(
        original_title="Upslope Spiked Snow Melt Juniper & Lime (355ml) / スパイクド スノーメルト",
        untappd_beer_name="Spiked Snow Melt Juniper And Lime",
        untappd_brewery_name="Upslope Brewing Company",
        untappd_style="Hard Seltzer",
        expected_brewery="Upslope Brewing Company"
    )
    assert passed_spiked is True, "Spiked Snow Melt should match Hard Seltzer style"

    # Hard Tea / Sparkling Tea (New Motion) should be accepted
    passed_hard_tea = validate_final_match(
        original_title="New Motion Hard Tea Mango Palmer (355ml)",
        untappd_beer_name="Mango Palmer Hard Sparkling Tea",
        untappd_brewery_name="New Motion Beverages",
        untappd_style="RTD - Hard Tea",
        expected_brewery="New Motion"
    )
    assert passed_hard_tea is True, "Hard Tea Mango Palmer should match RTD - Hard Tea style"


def test_validate_final_match_short_year_notation():
    # Short year '24 in title should match (2024) in Untappd beer name
    passed = validate_final_match(
        original_title="Himitsu Beer Pepper's Delight '24 350ml",
        untappd_beer_name="Pepper's Delight (2024)",
        untappd_brewery_name="Himitsu Beer",
        untappd_style="Farmhouse Ale - Saison",
        expected_brewery="Himitsu Beer"
    )
    assert passed is True, "Short year '24 should match (2024) in Untappd beer name"



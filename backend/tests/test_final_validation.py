import pytest
from backend.src.services.untappd.validators import validate_final_match, validate_brewery_match

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

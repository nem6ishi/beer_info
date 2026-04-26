"""
Tests for Untappd beer/brewery name validation logic.
Covers: validate_beer_match, validate_brewery_match, strip_beer_suffix,
        score_beer_match, has_variant_mismatch
"""
import unittest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.services.untappd.validators import validate_brewery_match, validate_beer_match, score_beer_match
from backend.src.services.untappd.text_utils import (
    strip_beer_suffix, has_variant_mismatch, extract_variant_modifiers,
    expand_abbreviations, normalize_for_comparison,
)
from backend.src.services.untappd.searcher import get_untappd_url


class TestStripBeerSuffix(unittest.TestCase):

    def test_removes_ipa_suffix(self):
        self.assertEqual(strip_beer_suffix("Amazing IPA"), "Amazing")

    def test_no_suffix_returns_none(self):
        self.assertIsNone(strip_beer_suffix("Regular Beer"))

    def test_full_style_name_returns_empty_stripped_to_none(self):
        # "Stout" is a suffix. After stripping "Amazing Stout" -> "Amazing"
        self.assertEqual(strip_beer_suffix("Amazing Stout"), "Amazing")

    def test_imperial_stout_suffix(self):
        # "Imperial Stout" is a suffix, strips to beer name
        self.assertEqual(strip_beer_suffix("Dark Imperial Stout"), "Dark")


class TestVariantModifiers(unittest.TestCase):
    """Tests for variant modifier detection and mismatch checking."""

    def test_extract_fresh_hop(self):
        mods = extract_variant_modifiers("Fresh Hop What Rough Beast")
        self.assertIn("freshhop", mods)

    def test_extract_barrel_aged(self):
        mods = extract_variant_modifiers("Bourbon Barrel Aged Imperial Stout")
        self.assertIn("bourbonbarrelaged", mods)
        self.assertIn("barrelaged", mods)

    def test_extract_no_modifiers(self):
        mods = extract_variant_modifiers("What Rough Beast")
        self.assertEqual(len(mods), 0)

    def test_extract_nitro(self):
        mods = extract_variant_modifiers("Nitro Milk Stout")
        self.assertIn("nitro", mods)

    def test_mismatch_fresh_hop_vs_base(self):
        """Fresh Hop variant should not match base beer."""
        self.assertTrue(has_variant_mismatch(
            "Fresh Hop What Rough Beast (2019)", "What Rough Beast"
        ))

    def test_no_mismatch_same_base(self):
        """Same base beer should match."""
        self.assertFalse(has_variant_mismatch(
            "What Rough Beast", "What Rough Beast"
        ))

    def test_no_mismatch_same_variant(self):
        """Same variant should match even with year difference."""
        self.assertFalse(has_variant_mismatch(
            "Fresh Hop What Rough Beast (2019)", "Fresh Hop What Rough Beast"
        ))

    def test_mismatch_barrel_aged_vs_base(self):
        """Barrel aged variant should not match base."""
        self.assertTrue(has_variant_mismatch(
            "Barrel Aged Dark Star", "Dark Star"
        ))

    def test_mismatch_nitro_vs_base(self):
        """Nitro variant should not match base."""
        self.assertTrue(has_variant_mismatch(
            "Nitro Milk Stout", "Milk Stout"
        ))

    def test_mismatch_coffee_vs_base(self):
        """Coffee variant should not match base."""
        self.assertTrue(has_variant_mismatch(
            "Coffee Imperial Stout", "Imperial Stout"
        ))


class TestValidateBreweryMatch(unittest.TestCase):

    def _make_element(self, brewery_text):
        soup = BeautifulSoup(f'<div class="beer-item"><div class="brewery">{brewery_text}</div></div>', 'lxml')
        return soup.select_one('.beer-item')

    def test_exact_match(self):
        self.assertTrue(validate_brewery_match(self._make_element("Stone Brewing"), "Stone Brewing"))

    def test_case_insensitive(self):
        self.assertTrue(validate_brewery_match(self._make_element("STONE BREWING"), "Stone Brewing"))

    def test_result_contains_expected(self):
        self.assertTrue(validate_brewery_match(self._make_element("Stone Brewing Co."), "Stone Brewing"))

    def test_expected_contains_result(self):
        self.assertTrue(validate_brewery_match(self._make_element("Stone"), "Stone Brewing"))

    def test_mismatch(self):
        self.assertFalse(validate_brewery_match(self._make_element("Modern Times"), "Stone Brewing"))

    def test_no_expected_brewery_passes(self):
        self.assertTrue(validate_brewery_match(self._make_element("Modern Times"), None))


class TestValidateBeerMatch(unittest.TestCase):

    def _make_element(self, beer_text):
        soup = BeautifulSoup(f'<div class="beer-item"><div class="name"><a href="/b/test/1">{beer_text}</a></div></div>', 'lxml')
        return soup.select_one('.beer-item')

    def test_exact_match(self):
        self.assertTrue(validate_beer_match(self._make_element("My Pale Ale"), "My Pale Ale"))

    def test_ordinal_match(self):
        # "11th Anniversary" on Untappd -> "eleventh anniversary" after normalization
        self.assertTrue(validate_beer_match(
            self._make_element("The Realm's Remedy Eleventh Anniversary IPA 2026"),
            "The Realm's Remedy 11th Anniversary IPA"
        ))

    def test_mismatch(self):
        self.assertFalse(validate_beer_match(self._make_element("Totally Different Beer"), "My Pale Ale"))

    def test_what_rough_beast_vs_fresh_hop(self):
        """THE core bug: 'What Rough Beast' must NOT match 'Fresh Hop What Rough Beast (2019)'."""
        self.assertFalse(validate_beer_match(
            self._make_element("Fresh Hop What Rough Beast (2019)"),
            "What Rough Beast"
        ))

    def test_what_rough_beast_exact(self):
        """'What Rough Beast' should match 'What Rough Beast'."""
        self.assertTrue(validate_beer_match(
            self._make_element("What Rough Beast"),
            "What Rough Beast"
        ))

    def test_fresh_hop_variant_self_match(self):
        """'Fresh Hop What Rough Beast' should match its own year variant."""
        self.assertTrue(validate_beer_match(
            self._make_element("Fresh Hop What Rough Beast (2019)"),
            "Fresh Hop What Rough Beast"
        ))

    def test_barrel_aged_variant_blocked(self):
        """Barrel Aged variant should not match base beer."""
        self.assertFalse(validate_beer_match(
            self._make_element("Barrel Aged Dark Lord"),
            "Dark Lord"
        ))

    def test_nitro_variant_blocked(self):
        """Nitro variant should not match base beer."""
        self.assertFalse(validate_beer_match(
            self._make_element("Nitro Milk Stout"),
            "Milk Stout"
        ))


class TestScoreBeerMatch(unittest.TestCase):

    def _make_element(self, beer_text):
        soup = BeautifulSoup(f'<div class="beer-item"><div class="name"><a href="/b/test/1">{beer_text}</a></div></div>', 'lxml')
        return soup.select_one('.beer-item')

    def test_exact_match_score_100(self):
        score = score_beer_match(self._make_element("What Rough Beast"), "What Rough Beast")
        self.assertEqual(score, 100)

    def test_variant_mismatch_score_0(self):
        score = score_beer_match(
            self._make_element("Fresh Hop What Rough Beast (2019)"),
            "What Rough Beast"
        )
        self.assertEqual(score, 0)

    def test_exact_beats_partial(self):
        """Exact match should score higher than partial match."""
        exact = score_beer_match(self._make_element("What Rough Beast"), "What Rough Beast")
        partial = score_beer_match(self._make_element("What Rough Beast (2023)"), "What Rough Beast")
        self.assertGreater(exact, partial)

    def test_no_expected_beer_returns_100(self):
        score = score_beer_match(self._make_element("Anything"), "")
        self.assertEqual(score, 100)

    def test_same_variant_with_year_has_positive_score(self):
        """Same variant with year should still match."""
        score = score_beer_match(
            self._make_element("Fresh Hop What Rough Beast (2019)"),
            "Fresh Hop What Rough Beast"
        )
        self.assertGreater(score, 0)

    def test_ddh_abbreviation_matches_expanded(self):
        """DDH Caligula should match Double Dry Hopped Caligula via abbreviation expansion."""
        score = score_beer_match(
            self._make_element("Double Dry Hopped Caligula"),
            "DDH Caligula"
        )
        self.assertEqual(score, 95)

    def test_tdh_abbreviation_matches_expanded(self):
        """TDH should match Triple Dry Hopped."""
        score = score_beer_match(
            self._make_element("Triple Dry Hopped Congress Street"),
            "TDH Congress Street"
        )
        self.assertEqual(score, 95)


class TestAbbreviationExpansion(unittest.TestCase):
    """Tests for expand_abbreviations utility."""

    def test_ddh_expansion(self):
        self.assertEqual(expand_abbreviations("DDH Caligula"), "double dry hopped Caligula")

    def test_tdh_expansion(self):
        self.assertEqual(expand_abbreviations("TDH IPA"), "triple dry hopped IPA")

    def test_no_expansion_for_normal_text(self):
        self.assertEqual(expand_abbreviations("What Rough Beast"), "What Rough Beast")

    def test_normalize_with_expansion(self):
        """normalize_for_comparison with expand_abbr=True should match DDH to expanded."""
        a = normalize_for_comparison("DDH Caligula", expand_abbr=True)
        b = normalize_for_comparison("Double Dry Hopped Caligula", expand_abbr=True)
        self.assertEqual(a, b)

@patch('backend.src.services.untappd.searcher.search_brewery_beer')
@patch('backend.src.services.untappd.searcher.search_brewery')
class TestGetUntappdUrl(unittest.TestCase):

    def test_returns_correct_match_via_brewery_search(self, mock_search_brewery, mock_search_beer):
        """When brewery URL is found and beer search returns a match."""
        mock_search_brewery.return_value = "https://untappd.com/MyBrewery"
        mock_search_beer.return_value = "https://untappd.com/b/my-brewery-mybeer/456"

        result = get_untappd_url("MyBrewery", "MyBeer")

        self.assertTrue(result['success'])
        self.assertEqual(result['url'], "https://untappd.com/b/my-brewery-mybeer/456")

    def test_returns_no_results_failure(self, mock_search_brewery, mock_search_beer):
        mock_search_brewery.return_value = None
        mock_search_beer.return_value = None

        result = get_untappd_url("NonExistentBrewery", "NonExistentBeer")

        self.assertFalse(result['success'])

    def test_prefers_exact_match_over_variant(self, mock_search_brewery, mock_search_beer):
        """When brewery search + scoring gives the exact match over the variant."""
        mock_search_brewery.return_value = "https://untappd.com/BreaksideBrewery"
        # The scoring-based search_brewery_beer should return the exact match
        mock_search_beer.return_value = "https://untappd.com/b/breakside-wrb/222"

        result = get_untappd_url("Breakside Brewery", "What Rough Beast")

        self.assertTrue(result['success'])
        self.assertEqual(result['url'], "https://untappd.com/b/breakside-wrb/222")

    @patch('ddgs.DDGS')
    def test_blocks_variant_when_no_exact_available(self, mock_ddgs_cls, mock_search_brewery, mock_search_beer):
        """When brewery search finds the brewery but beer search returns None (variant blocked)."""
        mock_search_brewery.return_value = "https://untappd.com/BreaksideBrewery"
        mock_search_beer.return_value = None  # Scoring blocked the variant
        # Mock DDG to return no results
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text.return_value = []
        mock_ddgs_cls.return_value = mock_ddgs_instance

        result = get_untappd_url("Breakside Brewery", "What Rough Beast")

        # Should fall through to DDG (mocked empty) and fail
        self.assertFalse(result['success'])


class TestSearchBreweryBeerScoring(unittest.TestCase):
    """Tests for search_brewery_beer with scoring integration."""

    def _make_html(self, results):
        """Build fake Untappd brewery beer list HTML."""
        items = ""
        for beer, href in results:
            items += f'''
            <div class="beer-item">
                <div class="name"><a href="{href}">{beer}</a></div>
            </div>'''
        return f"<html><body>{items}</body></html>"

    @patch('backend.src.services.untappd.http_client.requests.get')
    def test_scoring_selects_exact_over_variant(self, mock_get):
        """Scoring should prefer exact match over variant."""
        html = self._make_html([
            ("Fresh Hop What Rough Beast (2019)", "/b/breakside-fresh-hop-wrb/111"),
            ("What Rough Beast", "/b/breakside-wrb/222"),
        ])
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from backend.src.services.untappd.http_client import search_brewery_beer

        result = search_brewery_beer(
            "https://untappd.com/BreaksideBrewery",
            "What Rough Beast",
            score_beer_fn=score_beer_match,
            validate_beer="What Rough Beast",
        )
        self.assertEqual(result, "https://untappd.com/b/breakside-wrb/222")

    @patch('backend.src.services.untappd.http_client.requests.get')
    def test_scoring_blocks_variant_only(self, mock_get):
        """When only variant exists, scoring returns None."""
        html = self._make_html([
            ("Fresh Hop What Rough Beast (2019)", "/b/breakside-fresh-hop-wrb/111"),
        ])
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        from backend.src.services.untappd.http_client import search_brewery_beer

        result = search_brewery_beer(
            "https://untappd.com/BreaksideBrewery",
            "What Rough Beast",
            score_beer_fn=score_beer_match,
            validate_beer="What Rough Beast",
        )
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()


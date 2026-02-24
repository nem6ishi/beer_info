"""
Tests for Untappd beer/brewery name validation logic.
Covers: validate_beer_match, validate_brewery_match, strip_beer_suffix
"""
import unittest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.src.services.untappd.validators import validate_brewery_match, validate_beer_match
from backend.src.services.untappd.text_utils import strip_beer_suffix
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


@patch('backend.src.services.untappd.searcher.requests.get')
class TestGetUntappdUrl(unittest.TestCase):

    def _make_html(self, results):
        """Build fake Untappd search HTML with given (beer, brewery, href) tuples."""
        items = ""
        for beer, brewery, href in results:
            items += f'''
            <div class="beer-item">
                <div class="name"><a href="{href}">{beer}</a></div>
                <div class="brewery">{brewery}</div>
            </div>'''
        return f"<html><body>{items}</body></html>"

    def test_returns_correct_match_skipping_wrong_brewery(self, mock_get):
        html = self._make_html([
            ("MyBeer", "OtherBrewery", "/b/other-brewery-mybeer/123"),
            ("MyBeer", "MyBrewery", "/b/my-brewery-mybeer/456"),
        ])
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp

        result = get_untappd_url("MyBrewery", "MyBeer")

        self.assertTrue(result['success'])
        self.assertEqual(result['url'], "https://untappd.com/b/my-brewery-mybeer/456")

    def test_returns_no_results_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body></body></html>"
        mock_get.return_value = mock_resp

        result = get_untappd_url("NonExistentBrewery", "NonExistentBeer")

        self.assertFalse(result['success'])
        self.assertEqual(result['failure_reason'], 'no_results')


if __name__ == '__main__':
    unittest.main()

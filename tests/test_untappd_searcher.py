import unittest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.untappd_searcher import validate_brewery_match, strip_beer_suffix, get_untappd_url

class TestUntappdSearcher(unittest.TestCase):

    def test_strip_beer_suffix(self):
        self.assertEqual(strip_beer_suffix("Amazing IPA"), "Amazing")
        self.assertEqual(strip_beer_suffix("Hazy Double IPA"), "Hazy") # strips largest suffix "Double IPA" or "Hazy"? "Double IPA" is in list? yes.
        self.assertEqual(strip_beer_suffix("Regular Beer"), None)
        self.assertEqual(strip_beer_suffix("Stout"), None) # "Stout" is a suffix, so "Stout" endswith "Stout" -> "" -> strip() -> "" -> None if checks for empty?
        # Logic check: stripped_name = beer_name[:-len(suffix)].strip(). If result is empty string, is it treated as valid?
        # Code: if found_suffix and stripped_name: ... so empty string is False.
        # Let's test "Imperial Stout" -> "Imperial" (because "Imperial Stout" is suffix? or just "Stout"?)
        # "Imperial Stout" is in the suffix list. So it strips the whole thing -> "" -> False. Correct.
        
    def test_validate_brewery_match(self):
        # Mock soup element
        def create_mock_element(brewery_text):
            soup = BeautifulSoup(f'<div class="beer-item"><div class="brewery">{brewery_text}</div></div>', 'lxml')
            return soup.select_one('.beer-item')

        # Exact match
        self.assertTrue(validate_brewery_match(create_mock_element("Stone Brewing"), "Stone Brewing"))
        
        # Case insensitive
        self.assertTrue(validate_brewery_match(create_mock_element("STONE BREWING"), "Stone Brewing"))
        
        # Partial match (Result contains Expected)
        self.assertTrue(validate_brewery_match(create_mock_element("Stone Brewing Co."), "Stone Brewing"))
        
        # Partial match (Expected contains Result - less common but possible if we search short name)
        self.assertTrue(validate_brewery_match(create_mock_element("Stone"), "Stone Brewing"))
        
        # Mismatch
        self.assertFalse(validate_brewery_match(create_mock_element("Modern Times"), "Stone Brewing"))
        
        # No expected brewery
        self.assertTrue(validate_brewery_match(create_mock_element("Modern Times"), None))

    @patch('app.services.untappd_searcher.requests.get')
    def test_get_untappd_url_validation(self, mock_get):
        # Scenario: Search for "MyBeer" from "MyBrewery".
        # Result 1: "MyBeer" by "OtherBrewery" (Should be rejected)
        # Result 2: "MyBeer" by "MyBrewery" (Should be accepted)
        
        html = """
        <html>
        <body>
            <div class="beer-item">
                <div class="name"><a href="/b/other-brewery-mybeer/123">MyBeer</a></div>
                <div class="brewery">OtherBrewery</div>
            </div>
            <div class="beer-item">
                <div class="name"><a href="/b/my-brewery-mybeer/456">MyBeer</a></div>
                <div class="brewery">MyBrewery</div>
            </div>
        </body>
        </html>
        """
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html
        mock_get.return_value = mock_resp
        
        url = get_untappd_url("MyBrewery", "MyBeer")
        
        self.assertEqual(url, "https://untappd.com/b/my-brewery-mybeer/456")

if __name__ == '__main__':
    unittest.main()

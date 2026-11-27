import unittest
from unittest.mock import patch
from backend.src.services.llm.cache_resolver import LocalCacheResolver


class TestLocalCacheResolverTier2(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch.object(LocalCacheResolver, "_load_brewery_dictionary", return_value=None):
            with patch("backend.src.services.llm.cache_resolver.get_supabase_client", return_value=None):
                self.resolver = LocalCacheResolver()

        self.resolver.brewery_dict = {
            "block 15": {"name_en": "Block 15 Brewing Company", "name_jp": "ブロック15"},
            "lyric": {"name_en": "Lyric Brewing", "name_jp": None},
            "common space": {"name_en": "Common Space Brewery", "name_jp": "コモンスペース"},
            "decadent": {"name_en": "Decadent Ales", "name_jp": "デカダント"},
            "amakusa sonar beer": {"name_en": "AMAKUSA SONAR BEER", "name_jp": "天草ソナービール"},
        }

    async def test_maruho_standard_format(self):
        res = await self.resolver.resolve_tier2_dictionary_match("Nebula 473ml/block 15", "マルホ酒店")
        self.assertIsNotNone(res)
        self.assertEqual(res["brewery_name_en"], "Block 15 Brewing Company")
        self.assertEqual(res["beer_name_en"], "Nebula")
        self.assertEqual(res["beer_name_core"], "Nebula")

    async def test_maruho_collab_preserves_host_brewery(self):
        res = await self.resolver.resolve_tier2_dictionary_match(
            "Death Greets me Warm (collab w/Messorem) 473ml/Lyric", "マルホ酒店"
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["brewery_name_en"], "Lyric Brewing")
        self.assertEqual(res["beer_name_core"], "Death Greets me Warm")

    async def test_antenna_america_leading_brewery(self):
        res = await self.resolver.resolve_tier2_dictionary_match(
            "Common Space Fresh Pils of LA (473ml) / フレッシュ ピルス オブ LA", "Antenna America"
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["brewery_name_en"], "Common Space Brewery")
        self.assertEqual(res["beer_name_en"], "Fresh Pils of LA")

    async def test_ichigo_ichie_paren_leading_brewery(self):
        res = await self.resolver.resolve_tier2_dictionary_match(
            "デカダント　ブラック ラズベリー クリーム ポップ（Decadent Black Raspberry Cream Pop）",
            "一期一会～る",
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["brewery_name_en"], "Decadent Ales")
        self.assertEqual(res["beer_name_en"], "Black Raspberry Cream Pop")

    async def test_witch_craft_market_bracket_format(self):
        res = await self.resolver.resolve_tier2_dictionary_match(
            "[AMAKUSA SONAR BEER] ONE MIND/ ワンマインド", "WITCH CRAFT MARKET"
        )
        self.assertIsNotNone(res)
        self.assertEqual(res["brewery_name_en"], "AMAKUSA SONAR BEER")
        self.assertEqual(res["beer_name_en"], "ONE MIND")


if __name__ == "__main__":
    unittest.main()

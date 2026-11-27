import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.src.commands.enrich_untappd import UntappdEnricher
from backend.src.commands.enrich_extract import LLMEnricher


def test_clean_raw_title_for_search():
    assert (
        UntappdEnricher._clean_raw_title_for_search(
            "Local Craft Beer Faded for Science Too (473ml) / フェイデッド フォア サイエンス ツー",
            brewery="Local Craft Beer",
        )
        == "Faded for Science Too"
    )
    assert (
        UntappdEnricher._clean_raw_title_for_search(
            "【11/20出荷】Sheriff Marlon 473ml/Evil Twin",
            brewery="Evil Twin Brewing",
        )
        == "Sheriff Marlon"
    )
    assert (
        UntappdEnricher._clean_raw_title_for_search(
            "903 Brewers Cookie Dough Stout (355ml) / クッキードウ スタウト",
            brewery="903 Brewers",
        )
        == "Cookie Dough Stout"
    )


@pytest.mark.asyncio
async def test_process_beer_missing_maruho_format_parses_brewery_and_beer():
    with patch("backend.src.commands.enrich_untappd.get_supabase_client", return_value=MagicMock()):
        enricher = UntappdEnricher(mode="missing", offline=True)
        enricher.brewery_manager = None
        enricher.extractor = None

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.ilike.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"untappd_url": "https://untappd.com/b/stone-brewing-double-bastard-ale/12345"}]
        )
        enricher.supabase = mock_db

        beer = {
            "url": "https://maruho.shop/products/double-bastard-ale-2024-355ml-stone",
            "name": "Double Bastard Ale 2024 355ml/Stone",
            "product_type": "beer",
        }
        res = await enricher._process_beer_missing(beer)
        assert res is not None
        assert res["scraped_payload"]["untappd_url"] == "https://untappd.com/b/stone-brewing-double-bastard-ale/12345"
        assert res["gemini_payload"]["brewery_name_en"] == "Stone"
        assert res["gemini_payload"]["beer_name_en"] == "Double Bastard Ale 2024"


@pytest.mark.asyncio
async def test_process_beer_missing_skips_unextracted_japanese_title():
    with patch("backend.src.commands.enrich_untappd.get_supabase_client", return_value=MagicMock()), \
         patch("backend.src.commands.enrich_untappd.record_enrichment_failure") as mock_record:
        enricher = UntappdEnricher(mode="missing", offline=False)
        enricher.brewery_manager = None
        enricher.extractor = None

        unextracted_jp = {
            "url": "https://151l.shop/?pid=999999",
            "name": "ひみつビール ジンジャーホップ 350ml缶",
            "product_type": "beer",
        }
        res = await enricher._process_beer_missing(unextracted_jp)
        assert res is None
        mock_record.assert_not_called()


@pytest.mark.asyncio
async def test_process_beer_missing_resolves_failure_for_non_beer():
    with patch("backend.src.commands.enrich_untappd.get_supabase_client", return_value=MagicMock()), \
         patch("backend.src.commands.enrich_untappd.resolve_search_failure") as mock_resolve:
        enricher = UntappdEnricher(mode="missing", offline=False)
        enricher.brewery_manager = None
        enricher.extractor = None

        beer = {
            "url": "https://151l.shop/?pid=set-123",
            "name": "クラフトビール6種セット",
            "product_type": "set",
        }
        res = await enricher._process_beer_missing(beer)
        assert res is None
        mock_resolve.assert_called_once_with(enricher.supabase, "https://151l.shop/?pid=set-123")


@pytest.mark.asyncio
async def test_llm_enricher_api_error_does_not_record_gemini_no_info():
    with patch("backend.src.commands.enrich_extract.get_supabase_client", return_value=MagicMock()), \
         patch("backend.src.commands.enrich_extract.get_llm_extractor") as mock_get_ext, \
         patch("backend.src.commands.enrich_extract.BreweryManager", return_value=MagicMock(breweries=[], find_breweries_in_text=MagicMock(return_value=[]))), \
         patch("backend.src.commands.enrich_extract.record_enrichment_failure") as mock_record:
        mock_ext = MagicMock()
        mock_ext.extract_info = AsyncMock(return_value={"_api_error": True, "_error_message": "429 quota exceeded"})
        mock_get_ext.return_value = mock_ext

        enricher = LLMEnricher()
        status, payload = await enricher._process_item({
            "url": "https://example.com/beer1",
            "name": "Test IPA 350ml",
            "shop": "TestShop",
        })
        assert status == "api_error"
        assert payload is None
        mock_record.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_breweries_relinks_changed_slug_and_refreshes_view():
    from backend.src.commands.enrich_breweries import enrich_breweries, _extract_brewery_numeric_id

    assert _extract_brewery_numeric_id("https://untappd.com/w/minamishinshu-beer/13860") == "13860"
    assert _extract_brewery_numeric_id("https://untappd.com/GreatDaneBrewingSendai") is None

    mock_sb = MagicMock()
    existing_breweries = [
        {
            "id": "uuid-1",
            "untappd_url": "https://untappd.com/w/minamishinshu-beer-co/13860",
            "name_en": "Minamishinshu Beer (南信州ビール)",
            "updated_at": "2026-11-24T00:00:00+00:00",
        }
    ]
    with patch("backend.src.commands.enrich_breweries.get_supabase_client", return_value=mock_sb), \
         patch("backend.src.commands.enrich_breweries._fetch_all_rows_paginated", side_effect=[existing_breweries, []]), \
         patch("backend.src.commands.enrich_breweries.scrape_brewery_details", new_callable=AsyncMock) as mock_scrape, \
         patch("backend.src.commands.enrich_breweries.refresh_materialized_view") as mock_refresh:
        await enrich_breweries(
            limit=5,
            target_urls=["https://untappd.com/w/minamishinshu-beer/13860"],
        )
        # Fast-path relink by numeric ID should not even need scraping
        mock_scrape.assert_not_called()
        mock_sb.table.assert_any_call("untappd_data")
        mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_enrich_breweries_rejects_404_page_title():
    from backend.src.commands.enrich_breweries import enrich_breweries

    mock_sb = MagicMock()
    with patch("backend.src.commands.enrich_breweries.get_supabase_client", return_value=mock_sb), \
         patch("backend.src.commands.enrich_breweries._fetch_all_rows_paginated", side_effect=[[], []]), \
         patch("backend.src.commands.enrich_breweries.scrape_brewery_details", new_callable=AsyncMock, return_value={"brewery_name": "We couldn't find that page."}), \
         patch("backend.src.commands.enrich_breweries.refresh_materialized_view") as mock_refresh:
        await enrich_breweries(
            limit=5,
            target_urls=["https://untappd.com/w/nonexistent/999999"],
        )
        mock_sb.table.return_value.insert.assert_not_called()
        mock_refresh.assert_not_called()


def test_backoff_allows_weekly_retry_for_in_stock_but_not_sold_out():
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    old_8d = (now - timedelta(days=8)).isoformat()
    recent_2d = (now - timedelta(days=2)).isoformat()

    mock_sb = MagicMock()
    in_stock_res = MagicMock(data=[{"url": "https://shop.test/in-stock-old"}, {"url": "https://shop.test/in-stock-recent"}])
    fail_res = MagicMock(data=[
        {"product_url": "https://shop.test/in-stock-old", "search_attempts": 5, "last_failed_at": old_8d},
        {"product_url": "https://shop.test/in-stock-recent", "search_attempts": 5, "last_failed_at": recent_2d},
        {"product_url": "https://shop.test/sold-out-old", "search_attempts": 5, "last_failed_at": old_8d},
    ])

    def _table_side_effect(name):
        t = MagicMock()
        if name == "beer_info_view":
            t.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = in_stock_res
        elif name == "untappd_search_failures":
            t.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = fail_res
        return t

    mock_sb.table.side_effect = _table_side_effect

    with patch("backend.src.commands.enrich_untappd.get_supabase_client", return_value=mock_sb):
        enricher = UntappdEnricher(mode="missing", offline=True)
        enricher._preload_failure_history()

        assert "https://shop.test/in-stock-old" not in enricher.skip_urls_for_backoff
        assert "https://shop.test/in-stock-recent" in enricher.skip_urls_for_backoff
        assert "https://shop.test/sold-out-old" in enricher.skip_urls_for_backoff




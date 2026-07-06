import pytest
from unittest.mock import patch, MagicMock
from backend.src.services.store.brewery_manager import BreweryManager

@pytest.fixture
def mock_supabase():
    with patch('backend.src.services.store.brewery_manager.get_supabase_client') as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

def test_load_breweries(mock_supabase):
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": "1",
            "name_en": "West Coast Brewing",
            "name_jp": "",
            "aliases": ["WCB"],
            "untappd_url": "https://untappd.com/WestCoastBrewing"
        }
    ]
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

    manager = BreweryManager()
    assert len(manager.breweries) == 1
    assert "west coast brewing" in manager.brewery_index
    assert "wcb" in manager.brewery_index

def test_learn_brewery_alias_new_jp(mock_supabase):
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": "1",
            "name_en": "West Coast Brewing",
            "name_jp": "",
            "aliases": ["WCB"],
            "untappd_url": "https://untappd.com/WestCoastBrewing"
        }
    ]
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

    manager = BreweryManager()
    
    # Learn a Japanese alias
    result = manager.learn_brewery_alias(brewery_name_en="West Coast Brewing", new_alias="ウエストコーストブルーイング")
    assert result is True
    
    # Check updated memory state
    brewery = manager.brewery_index["west coast brewing"]
    assert brewery["name_jp"] == "ウエストコーストブルーイング"
    assert "ウエストコーストブルーイング" in brewery["aliases"]
    assert "ウエストコーストブルーイング" in manager.brewery_index
    
    # Check DB update was called
    mock_supabase.table.return_value.update.assert_called_once()

def test_learn_brewery_alias_already_known(mock_supabase):
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": "1",
            "name_en": "West Coast Brewing",
            "name_jp": "ウエストコーストブルーイング",
            "aliases": ["WCB", "ウエストコーストブルーイング"],
            "untappd_url": "https://untappd.com/WestCoastBrewing"
        }
    ]
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

    manager = BreweryManager()
    
    # Try learning already known alias
    result = manager.learn_brewery_alias(brewery_name_en="West Coast Brewing", new_alias="WCB")
    assert result is False
    
    # Try learning already known jp name
    result = manager.learn_brewery_alias(brewery_name_en="West Coast Brewing", new_alias="ウエストコーストブルーイング")
    assert result is False

def test_learn_brewery_alias_ignore_stopwords(mock_supabase):
    mock_response = MagicMock()
    mock_response.data = [
        {
            "id": "1",
            "name_en": "West Coast Brewing",
            "name_jp": "",
            "aliases": [],
            "untappd_url": "https://untappd.com/WestCoastBrewing"
        }
    ]
    mock_supabase.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_response

    manager = BreweryManager()
    
    # Try learning generic stopword
    result = manager.learn_brewery_alias(brewery_name_en="West Coast Brewing", new_alias="Brewery")
    assert result is False
    result = manager.learn_brewery_alias(brewery_name_en="West Coast Brewing", new_alias="Beer Co")
    assert result is False

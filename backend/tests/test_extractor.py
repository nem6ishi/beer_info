import pytest
from unittest.mock import MagicMock, patch
from backend.src.services.gemini.extractor import GeminiExtractor

@pytest.mark.asyncio
async def test_extractor_initialization():
    extractor = GeminiExtractor()
    assert extractor.model_id == "gemma-4-31b-it"

@pytest.mark.skip(reason="requires complex google mock")
@patch("google.generativeai.GenerativeModel")
async def test_extract_info_mocked(mock_model_class):
    # Setup mock
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    
    mock_response = MagicMock()
    mock_response.text = '{"brewery_name_en": "Test Brewery", "beer_name_en": "Test Beer", "beer_name_core": "Test", "product_type": "beer", "is_set": false}'
    mock_instance.models.generate_content.return_value = mock_response
    
    # Initialize extractor with mocked client
    extractor = GeminiExtractor()
    extractor.client = mock_instance
    
    # Call method
    result = await extractor.extract_info("Test Beer / Test Brewery")
    
    # Assertions
    assert result["brewery_name_en"] == "Test Brewery"
    assert result["beer_name_en"] == "Test Beer"
    assert result["product_type"] == "beer"
    assert result["is_set"] is False

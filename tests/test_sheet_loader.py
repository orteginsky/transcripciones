import pytest
from unittest.mock import MagicMock
from src.ingestion.sheet_loader import get_audio_links


def test_get_audio_links_with_values():
    # Mock del servicio de Sheets
    mock_sheets_service = MagicMock()
    mock_values_get = (
        mock_sheets_service.spreadsheets.return_value
        .values.return_value
        .get.return_value
    )
    mock_values_get.execute.return_value = {
        "values": [
            ["col1", "col2", "col3", "col4", "col5", "https://drive.google.com/file/d/12345/view"],
            ["a", "b", "c", "d", "e", "https://drive.google.com/file/d/67890/view"],
        ]
    }

    results = get_audio_links(mock_sheets_service, "fake_id", "Hoja1!A2:F100", link_col=5)

    assert len(results) == 2
    assert results[0]["row"] == 2
    assert results[0]["link"] == "https://drive.google.com/file/d/12345/view"
    assert results[1]["row"] == 3
    assert results[1]["link"].endswith("67890/view")


def test_get_audio_links_empty_values():
    mock_sheets_service = MagicMock()
    mock_sheets_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": []
    }

    results = get_audio_links(mock_sheets_service, "fake_id", "Hoja1!A2:F100")

    assert results == []


def test_get_audio_links_with_error():
    mock_sheets_service = MagicMock()
    mock_sheets_service.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = Exception("API error")

    results = get_audio_links(mock_sheets_service, "fake_id", "Hoja1!A2:F100")

    assert results == []

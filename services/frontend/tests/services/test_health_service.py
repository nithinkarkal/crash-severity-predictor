"""
Tests for health service
"""

from unittest.mock import MagicMock, patch

import requests

from services.frontend.src.models.health_model import HealthResponse
from services.frontend.src.services.health_service import get_health


def test_get_health_success() -> None:

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "healthy",
        "model_loaded": True,
        "model_name": "test_model",
    }

    with patch(
        "services.frontend.src.services.health_service.api_client.get",
        return_value=mock_response,
    ):
        result = get_health()

    assert isinstance(result, HealthResponse)
    assert result.status == "healthy"
    assert result.model_loaded is True
    assert result.model_name == "test_model"


def test_get_health_failure() -> None:
    with patch("services.frontend.src.services.health_service.api_client.get") as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        result = get_health()

        assert isinstance(result, HealthResponse)
        assert result.status == "offline"
        assert result.model_loaded is False
        assert result.model_name is None

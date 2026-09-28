"""
Tests for model info service
"""

from unittest.mock import MagicMock, patch

import requests

from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.services.model_info_service import get_model_info


def test_get_model_info_success() -> None:
    """Test successful model info retrieval."""

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "registry_name": "accident-models",
        "alias": "severity-predictor",
        "version": "1.0.0",
        "algorithm": "RandomForest",
        "trained_at": "2023-01-01T00:00:00Z",
        "dataset": "accident_data_v1",
        "features_count": 15,
        "metrics": {"accuracy": 0.92, "precision": 0.89, "recall": 0.87},
        "parameters": {"n_estimators": 100, "max_depth": 10},
    }
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.model_info_service.api_client.get",
        return_value=mock_response,
    ):
        result = get_model_info()

    assert isinstance(result, ModelInfo)
    assert result.registry_name == "accident-models"
    assert result.alias == "severity-predictor"
    assert result.version == "1.0.0"
    assert result.algorithm == "RandomForest"
    assert result.trained_at == "2023-01-01T00:00:00Z"
    assert result.dataset == "accident_data_v1"
    assert result.features_count == 15
    assert result.metrics["accuracy"] == 0.92
    assert result.parameters["n_estimators"] == 100


def test_get_model_info_request_exception() -> None:
    """Test model info retrieval with request exception."""

    with patch("services.frontend.src.services.model_info_service.api_client.get") as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        result = get_model_info()

    assert result is None


def test_get_model_info_http_error() -> None:
    """Test model info retrieval with HTTP error."""

    with patch("services.frontend.src.services.model_info_service.api_client.get") as mock_get:
        mock_response = MagicMock()
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.status_code = 500
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        result = get_model_info()

    assert result is None

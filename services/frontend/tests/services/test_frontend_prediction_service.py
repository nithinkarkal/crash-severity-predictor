"""
Tests for prediction service
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from services.frontend.src.models.prediction_model import PredictionResponse
from services.frontend.src.services.prediction_service import predict


def test_predict_success() -> None:
    """Test successful prediction request."""

    mock_response = MagicMock()
    mock_response.json.return_value = {"severity": "high", "severity_code": 3, "probability": 0.85, "model_used": "accident_model_v1"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.prediction_service.api_client.post",
        return_value=mock_response,
    ):
        result = predict({"feature1": 1.0, "feature2": 2.0}, "test-token")

    assert isinstance(result, PredictionResponse)
    assert result.severity == "high"
    assert result.severity_code == 3
    assert result.probability == 0.85
    assert result.model_used == "accident_model_v1"


def test_predict_http_error() -> None:
    """Test prediction request raises HTTPError."""

    with patch("services.frontend.src.services.prediction_service.api_client.post") as mock_post:
        mock_response = MagicMock()
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.status_code = 500
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            predict({"feature1": 1.0}, "test-token")


def test_predict_connection_error() -> None:
    """Test prediction request raises ConnectionError."""

    with patch("services.frontend.src.services.prediction_service.api_client.post") as mock_post:
        mock_post.side_effect = requests.exceptions.ConnectionError("no network")

        with pytest.raises(requests.exceptions.ConnectionError):
            predict({"feature1": 1.0}, "test-token")

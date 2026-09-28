"""
Integration tests for backend metrics route
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def test_metrics_returns_200(client: TestClient) -> None:
    """The /metrics endpoint should be publicly accessible and return 200."""

    response = client.get("/metrics")

    assert response.status_code == 200


def test_metrics_returns_prometheus_content_type(client: TestClient) -> None:
    """The /metrics endpoint should return Prometheus exposition format."""

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@patch("services.backend.src.routes.metrics.refresh_drift_metrics")
@patch("services.backend.src.routes.metrics.get_model_status")
def test_metrics_uses_loaded_model_version(
    mock_get_model_status: MagicMock,
    mock_refresh_drift_metrics: MagicMock,
    client: TestClient,
) -> None:
    """The endpoint should refresh drift metrics for the loaded model version."""

    mock_get_model_status.return_value = {
        "loaded": True,
        "name": "accident-severity-predictor@production (v7)",
        "alias": "production",
        "features_count": 29,
    }

    response = client.get("/metrics")

    assert response.status_code == 200
    mock_get_model_status.assert_called_once_with()
    mock_refresh_drift_metrics.assert_called_once_with("accident-severity-predictor@production (v7)")


@patch("services.backend.src.routes.metrics.refresh_drift_metrics")
@patch("services.backend.src.routes.metrics.get_model_status")
def test_metrics_uses_unknown_when_model_not_loaded(
    mock_get_model_status: MagicMock,
    mock_refresh_drift_metrics: MagicMock,
    client: TestClient,
) -> None:
    """The endpoint should use 'unknown' when no model is currently loaded."""

    mock_get_model_status.return_value = {
        "loaded": False,
        "name": None,
        "alias": None,
        "features_count": 0,
    }

    response = client.get("/metrics")

    assert response.status_code == 200
    mock_get_model_status.assert_called_once_with()
    mock_refresh_drift_metrics.assert_called_once_with("unknown")


def test_metrics_contains_custom_metrics(
    client: TestClient,
) -> None:
    """The endpoint should expose metrics registered in the custom registry."""

    response = client.get("/metrics")

    assert response.status_code == 200

    body = response.text

    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "predictions_total" in body
    assert "prediction_confidence" in body
    assert "prediction_duration_seconds" in body
    assert "model_loaded" in body
    assert "model_reload_total" in body
    assert "model_f1_score" in body
    assert "model_drift_share" in body
    assert "model_dataset_drift_detected" in body


@patch("services.backend.src.routes.metrics.refresh_drift_metrics")
@patch("services.backend.src.routes.metrics.get_model_status")
def test_metrics_does_not_require_authentication(
    mock_get_model_status: MagicMock,
    mock_refresh_drift_metrics: MagicMock,
    client: TestClient,
) -> None:
    """The /metrics endpoint should be accessible without a bearer token."""

    mock_get_model_status.return_value = {
        "loaded": False,
        "name": None,
        "alias": None,
        "features_count": 0,
    }

    response = client.get("/metrics")

    assert response.status_code == 200
    mock_get_model_status.assert_called_once()
    mock_refresh_drift_metrics.assert_called_once_with("unknown")


@patch("services.backend.src.routes.metrics.refresh_drift_metrics")
@patch("services.backend.src.routes.metrics.get_model_status")
def test_metrics_refresh_failure_propagates(
    mock_get_model_status: MagicMock,
    mock_refresh_drift_metrics: MagicMock,
    client: TestClient,
) -> None:
    """Unexpected errors from drift metric refresh should propagate."""

    mock_get_model_status.return_value = {
        "loaded": True,
        "name": "model-v1",
        "alias": "production",
        "features_count": 29,
    }
    mock_refresh_drift_metrics.side_effect = RuntimeError("refresh failed")

    with pytest.raises(RuntimeError, match="refresh failed"):
        client.get("/metrics")

    mock_get_model_status.assert_called_once_with()
    mock_refresh_drift_metrics.assert_called_once_with("model-v1")

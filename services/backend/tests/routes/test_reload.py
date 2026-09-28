"""
Tests for the model-reload endpoint (POST /api/v1/model/reload).

The endpoint reuses prediction_service.load_model(force_reload=True); here we mock
that loader so no real MLflow/registry access happens.
"""

from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient


def test_reload_success(client: TestClient) -> None:
    """A successful reload returns 200 with the new model status."""
    with (
        patch("services.backend.src.routes.reload.load_model") as mock_load,
        patch(
            "services.backend.src.routes.reload.get_model_status",
            return_value={
                "loaded": True,
                "name": "accident-severity-predictor@production (v8)",
                "alias": "production",
                "features_count": 29,
            },
        ),
    ):
        resp = client.post("/api/v1/model/reload")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reloaded"
    assert body["model"]["name"].endswith("(v8)")
    mock_load.assert_called_once_with(force_reload=True)


def test_reload_propagates_503_when_no_model(client: TestClient) -> None:
    """If loading fails (no model / registry down), the 503 from load_model surfaces."""
    with patch(
        "services.backend.src.routes.reload.load_model",
        side_effect=HTTPException(status_code=503, detail="no model"),
    ):
        resp = client.post("/api/v1/model/reload")

    assert resp.status_code == 503

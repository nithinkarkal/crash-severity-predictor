"""
Integration tests for backend train route
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@patch("services.backend.src.routes.train._train_and_reload")
def test_train_trigger(mock_train: MagicMock, client: TestClient, override_admin: None) -> None:
    """train endpoint returns immediately with 'started' status."""

    response = client.post("/api/v1/train", json={"model_name": "model_20260723000000"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["model_name"] == "model_20260723000000"
    assert "background" in data["message"].lower()
    mock_train.assert_called_once()

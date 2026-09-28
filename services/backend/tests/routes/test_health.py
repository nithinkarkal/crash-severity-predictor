"""
Integration tests for backend health route
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("loaded", "name", "expected_loaded", "expected_name"),
    [
        (False, None, False, None),
        (
            True,
            "accident-severity-predictor@production (v7)",
            True,
            "accident-severity-predictor@production (v7)",
        ),
    ],
)
def test_health(client: TestClient, loaded: bool, name: str | None, expected_loaded: bool, expected_name: str | None) -> None:
    """health endpoint should reflect model loading status"""

    with patch(
        "services.backend.src.routes.health.get_model_status",
        return_value={"loaded": loaded, "name": name, "alias": "production" if loaded else None, "features_count": 29 if loaded else 0},
    ):
        response = client.get("/api/v1/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is expected_loaded
        assert data["model_name"] == expected_name

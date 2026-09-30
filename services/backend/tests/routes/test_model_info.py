"""
Integration tests for the backend /model/info route.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@patch("services.backend.src.routes.model_info.get_model_info")
def test_model_info_success(mock_info: MagicMock, client: TestClient) -> None:
    """/model/info returns model metadata including feature importances."""
    mock_info.return_value = {
        "registry_name": "crash-severity-predictor",
        "alias": "production",
        "version": "10",
        "algorithm": "RandomForestClassifier",
        "trained_at": "unknown",
        "dataset": "BAAC 2021-2023",
        "features_count": 28,
        "metrics": {},
        "parameters": {"n_estimators": 100, "max_depth": 20},
        "feature_importance": {"vma": 0.12, "secu1": 0.10},
    }

    response = client.get("/api/v1/model/info")

    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "RandomForestClassifier"
    assert data["version"] == "10"
    assert data["feature_importance"]["vma"] == 0.12

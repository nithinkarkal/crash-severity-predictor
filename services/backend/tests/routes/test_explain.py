"""
Integration tests for the backend /explain route (SHAP feature contributions).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from services.backend.src.schemas.prediction import ExplanationResponse, FeatureContribution


def _fake_explanation() -> ExplanationResponse:
    return ExplanationResponse(
        severity="Injured (hospitalized) / Killed",
        severity_code=1,
        probability=0.83,
        base_value=0.35,
        summary="Likely a severe or fatal injury (83% confidence). Main factors increasing this risk: speed limit (vma=110).",
        top_features=[
            FeatureContribution(feature="vma", value=110.0, shap_value=0.12, direction="increases"),
            FeatureContribution(feature="secu1", value=0.0, shap_value=-0.07, direction="decreases"),
        ],
        model_used="model_test",
    )


@patch("services.backend.src.routes.explain.explain_accident")
def test_explain_success(mock_explain: MagicMock, client: TestClient, valid_payload: dict, override_user: None) -> None:
    """/explain returns the predicted class plus ranked feature contributions."""
    mock_explain.return_value = _fake_explanation()

    response = client.post("/api/v1/explain", json=valid_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["severity_code"] == 1
    assert data["base_value"] == 0.35
    assert data["top_features"][0]["feature"] == "vma"
    assert data["top_features"][0]["direction"] == "increases"
    assert "confidence" in data["summary"]


def test_plain_language_summary_wording() -> None:
    """The plain-language summary reads naturally and splits increasing vs lowering factors."""
    from services.backend.src.services.prediction_service import _plain_language_summary

    top = [
        FeatureContribution(feature="vma", value=110.0, shap_value=0.20, direction="increases"),
        FeatureContribution(feature="secu1", value=0.0, shap_value=0.10, direction="increases"),
        FeatureContribution(feature="lum", value=1.0, shap_value=-0.05, direction="decreases"),
    ]
    summary = _plain_language_summary(severity_code=1, probability=0.83, top_features=top)

    assert summary.startswith("Likely a severe or fatal injury (83% confidence).")
    assert "increasing this risk" in summary
    assert "speed limit (vma=110)" in summary
    assert "lowering the risk" in summary
    assert "lighting conditions (lum=1)" in summary


@patch("services.backend.src.routes.explain.explain_accident")
def test_explain_respects_top_n_query(mock_explain: MagicMock, client: TestClient, valid_payload: dict, override_user: None) -> None:
    """The top_n query param is forwarded to the service."""
    mock_explain.return_value = _fake_explanation()

    response = client.post("/api/v1/explain?top_n=3", json=valid_payload)

    assert response.status_code == 200
    assert mock_explain.call_args.kwargs.get("top_n") == 3


def test_explain_validation_error(client: TestClient, override_user: None) -> None:
    """Invalid payloads return 422 before the model is ever called."""
    response = client.post("/api/v1/explain", json={"place": 999})
    assert response.status_code == 422


def test_explain_bad_top_n(client: TestClient, valid_payload: dict, override_user: None) -> None:
    """top_n below 1 is rejected by query validation."""
    response = client.post("/api/v1/explain?top_n=0", json=valid_payload)
    assert response.status_code == 422

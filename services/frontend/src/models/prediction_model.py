"""Prediction API response models."""

from pydantic import BaseModel


class PredictionResponse(BaseModel):
    """prediction result returned by the backend."""

    severity: str
    severity_code: int
    probability: float | None = None
    probabilities: dict[int, float] = {}
    model_used: str


class FeatureContribution(BaseModel):
    """A single feature's SHAP contribution to one prediction."""

    feature: str
    value: float
    shap_value: float
    direction: str


class ExplanationResponse(BaseModel):
    """per-prediction explanation returned by the backend /explain endpoint."""

    severity: str
    severity_code: int
    probability: float | None = None
    base_value: float
    summary: str
    top_features: list[FeatureContribution] = []
    model_used: str

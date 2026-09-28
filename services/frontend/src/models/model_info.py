"""
Model information response model.
"""

from typing import Any

from pydantic import BaseModel


class ModelInfo(BaseModel):
    registry_name: str
    alias: str
    version: str
    algorithm: str
    trained_at: str
    dataset: str
    features_count: int
    metrics: dict[str, float]
    parameters: dict[str, Any]
    feature_importance: dict[str, float] = {}

"""
Model metadata schemas
"""

from typing import Any

from pydantic import BaseModel, Field


class ModelInfoResponse(BaseModel):
    """
    metadata for the currently served production model
    """

    registry_name: str
    alias: str
    version: str
    algorithm: str
    trained_at: str
    dataset: str
    features_count: int
    metrics: dict[str, float]
    parameters: dict[str, Any]
    feature_importance: dict[str, float] = Field(default_factory=dict)

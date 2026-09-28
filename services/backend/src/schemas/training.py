"""
Training schema backend API
"""

from pydantic import BaseModel, Field


class TrainRequest(BaseModel):
    """Request body for training trigger."""

    model_name: str | None = Field(
        default=None,
        description="Model name (None = auto-resolve latest)",
    )


class TrainResponse(BaseModel):
    """Training result."""

    status: str
    model_name: str
    message: str

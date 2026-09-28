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


class TrainStatusResponse(BaseModel):
    """Live status of the most recent training run (polled by the GUI)."""

    state: str = Field(description="idle | running | succeeded | failed")
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    model_name: str | None = None
    version: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    message: str = ""
    error: str | None = None

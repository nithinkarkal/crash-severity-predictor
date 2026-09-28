"""Training API response model."""

from pydantic import BaseModel


class TrainResponse(BaseModel):
    """training trigger result returned by the backend /train endpoint."""

    status: str
    model_name: str
    message: str


class TrainStatusResponse(BaseModel):
    """live status of the most recent training run (from /train/status)."""

    state: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    model_name: str | None = None
    version: str | None = None
    metrics: dict[str, float] = {}
    message: str = ""
    error: str | None = None

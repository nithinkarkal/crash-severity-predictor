"""
Backend Health endpoint
"""

from fastapi import APIRouter

from services.backend.src.schemas.prediction import HealthResponse
from services.backend.src.services.prediction_service import get_model_status

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """check API health and model loading status."""
    status = get_model_status()
    return HealthResponse(
        status="healthy",
        model_loaded=status["loaded"],
        model_name=status["name"],
    )

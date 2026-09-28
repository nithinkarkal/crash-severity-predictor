"""
Model metadata routes
"""

from fastapi import APIRouter

from services.backend.src.schemas.model_info import ModelInfoResponse
from services.backend.src.services.prediction_service import get_model_info

router = APIRouter(prefix="/api/v1", tags=["Model"])


@router.get("/model/info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    """return metadata for the currently served production model"""
    return ModelInfoResponse(**get_model_info())

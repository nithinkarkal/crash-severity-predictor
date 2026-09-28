"""
Backend prediction endpoint
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from services.backend.src.core.auth import get_current_user
from services.backend.src.schemas.auth import UserCredentials
from services.backend.src.schemas.prediction import PredictionRequest, PredictionResponse
from services.backend.src.services.prediction_service import predict_accident

router = APIRouter(prefix="/api/v1", tags=["Prediction"])


@router.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest, current_user: Annotated[UserCredentials, Depends(get_current_user)]) -> PredictionResponse:
    """
    predict accident severity from input features.

    Requires a trained model to be available in artifacts/models/.
    """
    return predict_accident(request)

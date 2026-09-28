"""
Backend explanation endpoint.

Returns per-feature SHAP contributions for a single prediction, so a user can see
*why* the model predicted a given severity — not just the label.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from services.backend.src.core.auth import get_current_user
from services.backend.src.schemas.auth import UserCredentials
from services.backend.src.schemas.prediction import ExplanationResponse, PredictionRequest
from services.backend.src.services.prediction_service import explain_accident

router = APIRouter(prefix="/api/v1", tags=["Prediction"])


@router.post("/explain", response_model=ExplanationResponse)
def explain(
    request: PredictionRequest,
    current_user: Annotated[UserCredentials, Depends(get_current_user)],
    top_n: Annotated[int, Query(ge=1, le=30, description="how many top features to return")] = 10,
) -> ExplanationResponse:
    """
    Explain an accident-severity prediction with SHAP feature contributions.

    Requires a trained model to be available (same model as /predict).
    """
    return explain_accident(request, top_n=top_n)

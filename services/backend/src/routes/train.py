"""
Backend training endpoint.

Triggers the training container asynchronously via BackgroundTasks.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends

from common.utils.asp_logging import get_logger
from services.backend.src.core.auth import require_admin
from services.backend.src.schemas.auth import UserCredentials
from services.backend.src.schemas.training import TrainRequest, TrainResponse
from services.backend.src.services.prediction_service import load_model
from services.backend.src.services.training_service import run_training_container

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Training"])


@router.post("/train", response_model=TrainResponse)
def train(
    request: TrainRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[UserCredentials, Depends(require_admin)],
) -> TrainResponse:
    """
    Trigger model training in a background Docker container.

    model_name behavior:
    - Explicit name (e.g. "model") -> train new version from this base
    - None -> auto-resolve from latest existing model, or default to "model"

    Training reads from data/processed/ and writes to artifacts/.
    If processed data is missing, the training container will fail with its own error.
    """
    background_tasks.add_task(
        _train_and_reload,
        model_name=request.model_name,
    )

    return TrainResponse(
        status="started",
        model_name=request.model_name or "auto-resolved",
        message="Training container launched in background. Check logs for progress.",
    )


def _train_and_reload(model_name: str | None) -> None:
    """Internal helper: run training then reload model."""
    try:
        result = run_training_container(model_name=model_name)
        logger.info(f"Training succeeded: {result['model_name']}")
        load_model(force_reload=True)
    except RuntimeError:
        # already logged in training_service
        pass

"""
Backend training endpoints.

- POST /train        -> trigger training in a background Docker container (admin only)
- GET  /train/status -> poll the latest run's live status (admin only)

Training is asynchronous (it can take minutes), so POST returns immediately and the GUI
polls /train/status to see running -> succeeded/failed, the resulting model + metrics.
"""

import os
from typing import Annotated

import requests
from fastapi import APIRouter, BackgroundTasks, Depends

from common.utils.asp_logging import get_logger
from services.backend.src.core.auth import require_admin
from services.backend.src.schemas.auth import UserCredentials
from services.backend.src.schemas.training import TrainRequest, TrainResponse, TrainStatusResponse
from services.backend.src.services.prediction_service import get_model_info, load_model
from services.backend.src.services.training_service import (
    _utc_now,
    get_training_status,
    run_training_container,
    set_training_status,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Training"])


def _notify_slack(text: str) -> None:
    """Best-effort Slack notification (no-op if SLACK_WEBHOOK_URL is unset). Never raises."""
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        return
    try:
        requests.post(url, json={"text": text}, timeout=10)
    except Exception as exc:  # noqa: BLE001 - alerting must never break training
        logger.warning(f"Slack notification failed: {exc}")


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
    """
    # Mark the run as running immediately so the GUI reflects it on the next poll.
    set_training_status(
        state="running",
        started_at=_utc_now(),
        finished_at=None,
        duration_seconds=None,
        model_name=request.model_name or "auto-resolved",
        version=None,
        metrics={},
        message="Training container launching...",
        error=None,
    )

    background_tasks.add_task(
        _train_and_reload,
        model_name=request.model_name,
    )

    return TrainResponse(
        status="started",
        model_name=request.model_name or "auto-resolved",
        message="Training container launched in background. Poll /train/status for progress.",
    )


@router.get("/train/status", response_model=TrainStatusResponse)
def train_status(
    current_user: Annotated[UserCredentials, Depends(require_admin)],
) -> TrainStatusResponse:
    """Return the live status of the most recent training run."""
    return TrainStatusResponse(**get_training_status())


def _train_and_reload(model_name: str | None) -> None:
    """Internal helper: run training, reload the model, and record the outcome."""
    try:
        result = run_training_container(model_name=model_name)
        load_model(force_reload=True)
        info = get_model_info()

        metrics = info.get("metrics", {})
        set_training_status(
            state="succeeded",
            finished_at=_utc_now(),
            duration_seconds=result.get("duration_seconds"),
            model_name=result.get("model_name"),
            version=info.get("version"),
            metrics=metrics,
            message="Training completed and the API reloaded the current production model.",
            error=None,
        )
        logger.info(f"Training succeeded: {result.get('model_name')}")
        _notify_slack(
            f":white_check_mark: ASP training succeeded — {result.get('model_name')} "
            f"(F1 {metrics.get('f1_score', 'n/a')}, {result.get('duration_seconds')}s)."
        )

    except Exception as exc:  # noqa: BLE001 - record any failure for the GUI, never crash the worker
        set_training_status(
            state="failed",
            finished_at=_utc_now(),
            message="Training failed.",
            error=str(exc),
        )
        logger.error(f"Training failed: {exc}")
        _notify_slack(f":x: ASP training failed: {exc}")

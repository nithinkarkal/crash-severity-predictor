"""Frontend training service (admin-triggered retraining)."""

from __future__ import annotations

import requests

from common.utils.asp_logging import get_logger
from services.frontend.src.models.training_model import TrainResponse, TrainStatusResponse
from services.frontend.src.services.api import api_client

logger = get_logger(__name__)


def trigger_training(model_name: str | None, token: str) -> TrainResponse:
    """Trigger a backend training run (admin only).

    Raises:
        requests.exceptions.HTTPError: backend returned an error (e.g. 403 non-admin).
        requests.exceptions.RequestException: backend unreachable.
        ValueError: response did not match TrainResponse.
    """

    response = api_client.post(
        "/train",
        json={"model_name": model_name},
        token=token,
    )
    response.raise_for_status()
    return TrainResponse.model_validate(response.json())


def get_training_status(token: str) -> TrainStatusResponse | None:
    """Fetch the live status of the latest training run. Returns None on any failure."""
    try:
        response = api_client.get("/train/status", token=token)
        response.raise_for_status()
        return TrainStatusResponse.model_validate(response.json())
    except (requests.exceptions.RequestException, ValueError) as exc:
        logger.warning("Could not fetch training status: %s", exc)
        return None

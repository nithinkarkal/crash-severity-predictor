"""Frontend prediction service."""

from __future__ import annotations

import requests

from common.utils.asp_logging import get_logger
from services.frontend.src.models.prediction_model import PredictionResponse
from services.frontend.src.services.api import api_client

logger = get_logger(__name__)


def predict(
    payload: dict,
    token: str,
) -> PredictionResponse:
    """send a prediction request to the backend.

    Raises:
        requests.exceptions.HTTPError:
            If the backend returns an HTTP error response.
        requests.exceptions.RequestException:
            If the request cannot reach the backend.
        ValueError:
            If the backend response does not match PredictionResponse.
    """

    try:
        response = api_client.post(
            "/predict",
            json=payload,
            token=token,
        )

        response.raise_for_status()

        return PredictionResponse.model_validate(response.json())

    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"

        logger.error(
            "Prediction request failed with HTTP %s",
            status_code,
        )

        raise

    except requests.exceptions.RequestException as exc:
        logger.error(
            "Prediction request failed: %s",
            exc,
        )

        raise

    except ValueError as exc:
        logger.error(
            "Invalid prediction response from backend: %s",
            exc,
        )

        raise

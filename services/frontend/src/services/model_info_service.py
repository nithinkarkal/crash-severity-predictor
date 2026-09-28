"""
Frontend model metadata service
"""

import requests

from common.utils.asp_logging import get_logger
from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.services.api import api_client

logger = get_logger(__name__)


def get_model_info() -> ModelInfo | None:
    """fetch metadata for the currently served model"""

    try:
        response = api_client.get("/model/info")
        response.raise_for_status()

        return ModelInfo.model_validate(response.json())
    except requests.exceptions.RequestException as exc:
        logger.error(f"Failed to fetch model info: {exc}")
        return None

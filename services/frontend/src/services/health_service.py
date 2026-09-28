"""
frontend api health check
"""

import requests

from common.utils.asp_logging import get_logger
from services.frontend.src.models.health_model import HealthResponse
from services.frontend.src.services.api import api_client

logger = get_logger(__name__)


def get_health() -> HealthResponse:

    try:
        response = api_client.get("/health")
        response.raise_for_status()

        return HealthResponse.model_validate(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch health: {e}")
        # backend unreachable or unhealthy
        return HealthResponse(status="offline", model_loaded=False, model_name=None)

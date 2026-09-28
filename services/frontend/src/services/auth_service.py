"""Frontend authentication service."""

import requests

from common.utils.asp_logging import get_logger
from services.frontend.src.models.auth_model import TokenResponse
from services.frontend.src.services.api import api_client

logger = get_logger(__name__)


def login(username: str, password: str) -> TokenResponse | None:
    """authenticate against the backend and return the JWT."""

    try:
        response = api_client.post(
            "/login",
            data={
                "username": username,
                "password": password,
            },
        )

        response.raise_for_status()

        return TokenResponse.model_validate(response.json())

    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            return None

        logger.error(f"Authentication failed: {exc}")
        return None

    except requests.exceptions.RequestException as exc:
        logger.error(f"Authentication request failed: {exc}")
        return None

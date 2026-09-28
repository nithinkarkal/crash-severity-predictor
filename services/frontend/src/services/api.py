"""
frontend api service
"""

import requests

from services.frontend.src.config.settings import settings


class APIService:
    def __init__(self) -> None:
        self.base_url = settings.backend_url + settings.api_prefix
        self.session = requests.Session()  # to save api access session

    def get(
        self,
        endpoint: str,
        token: str | None = None,
    ) -> requests.Response:
        headers = self._auth_headers(token)

        return self.session.get(
            self.base_url + endpoint,
            headers=headers,
            timeout=3,
        )

    def post(
        self,
        endpoint: str,
        *,
        data: dict | None = None,
        json: dict | None = None,
        token: str | None = None,
    ) -> requests.Response:

        headers = self._auth_headers(token)

        return self.session.post(
            self.base_url + endpoint,
            data=data,
            json=json,
            headers=headers,
            timeout=10,
        )

    @staticmethod
    def _auth_headers(token: str | None) -> dict[str, str]:
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}


api_client = APIService()

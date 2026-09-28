"""Unit tests for services.frontend.src.services.auth_service."""

from unittest.mock import MagicMock, patch

import requests

from services.frontend.src.services import auth_service


class TestLogin:
    """Tests for auth_service.login()."""

    @patch("services.frontend.src.services.auth_service.api_client.post")
    def test_login_success(self, mock_post: MagicMock) -> None:
        """login returns a TokenResponse when the backend authenticates the user."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"access_token": "tok-123", "token_type": "bearer"}
        mock_post.return_value = mock_response

        result = auth_service.login("admin", "secret")

        assert result is not None
        assert result.access_token == "tok-123"
        assert result.token_type == "bearer"
        mock_post.assert_called_once_with(
            "/login",
            data={"username": "admin", "password": "secret"},
        )

    @patch("services.frontend.src.services.auth_service.api_client.post")
    def test_login_401_failure(self, mock_post: MagicMock) -> None:
        """login returns None when the backend rejects credentials (401)."""
        mock_response = MagicMock()
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.status_code = 401
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_response

        result = auth_service.login("admin", "wrong")

        assert result is None

    @patch("services.frontend.src.services.auth_service.api_client.post")
    def test_login_network_error(self, mock_post: MagicMock) -> None:
        """login returns None when a network-level RequestException occurs."""
        mock_post.side_effect = requests.exceptions.ConnectionError("no network")

        result = auth_service.login("admin", "secret")

        assert result is None

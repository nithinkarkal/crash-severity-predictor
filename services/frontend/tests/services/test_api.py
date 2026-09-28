"""
Tests for API service
"""

from unittest.mock import MagicMock, patch

from services.frontend.src.services.api import api_client


def test_api_get_success() -> None:
    """Test successful GET request."""

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.api.api_client.session.get",
        return_value=mock_response,
    ):
        response = api_client.get("/test-endpoint", token="test-token")

    assert response.json() == {"status": "ok"}


def test_api_post_success() -> None:
    """Test successful POST request."""

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": "success"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.api.api_client.session.post",
        return_value=mock_response,
    ):
        response = api_client.post("/test-endpoint", json={"data": "test"}, token="test-token")

    assert response.json() == {"result": "success"}


def test_api_post_with_data() -> None:
    """Test POST request with data parameter."""

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": "success"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.api.api_client.session.post",
        return_value=mock_response,
    ):
        response = api_client.post("/test-endpoint", data={"field": "value"}, token="test-token")

    assert response.json() == {"result": "success"}


def test_api_get_without_token() -> None:
    """Test GET request without token."""

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ok"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.api.api_client.session.get",
        return_value=mock_response,
    ):
        response = api_client.get("/test-endpoint")

    assert response.json() == {"status": "ok"}


def test_api_post_without_token() -> None:
    """Test POST request without token."""

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": "success"}
    mock_response.raise_for_status.return_value = None

    with patch(
        "services.frontend.src.services.api.api_client.session.post",
        return_value=mock_response,
    ):
        response = api_client.post("/test-endpoint", json={"data": "test"})

    assert response.json() == {"result": "success"}

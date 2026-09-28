"""
Tests for login page
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import streamlit as st

from services.frontend.src.models.auth_model import TokenResponse
from services.frontend.src.pages.login import login_page

COLS = (MagicMock(), MagicMock(), MagicMock())
SESSION = MagicMock()


def _widget_stacks(**kwargs) -> ExitStack:
    """Apply the streamlit widget patches needed by login_page."""
    stack = ExitStack()
    stack.enter_context(patch.object(st, "columns", return_value=COLS))
    stack.enter_context(patch.object(st, "form", return_value=MagicMock()))
    stack.enter_context(patch.object(st, "text_input", side_effect=[kwargs.get("username", "admin"), kwargs.get("password", "secret")]))
    stack.enter_context(patch.object(st, "checkbox", return_value=kwargs.get("remember", True)))
    stack.enter_context(patch.object(st, "form_submit_button", return_value=kwargs.get("submitted", True)))
    stack.enter_context(patch.object(st, "session_state", SESSION))
    return stack


def test_login_page_success() -> None:
    """Test successful login sets the session and navigates."""

    mock_token = MagicMock(spec=TokenResponse)
    mock_token.access_token = "test-token"
    SESSION.get.return_value = "Monitoring"

    with _widget_stacks():
        with (
            patch(
                "services.frontend.src.pages.login.login",
                return_value=mock_token,
            ) as mock_login,
            patch("services.frontend.src.pages.login.set_authenticated_session") as mock_set_session,
            patch.object(st, "rerun") as mock_rerun,
        ):
            login_page()

    mock_login.assert_called_once_with("admin", "secret")
    mock_set_session.assert_called_once_with(
        token="test-token",
        username="admin",
        remember_me=True,
    )
    assert SESSION.page == "Monitoring"
    assert SESSION.post_login_page == "Home"
    mock_rerun.assert_called_once()


def test_login_page_invalid_credentials() -> None:
    """Test failed login shows an error and skips the session."""

    messages = []
    with _widget_stacks(remember=False):
        with (
            patch(
                "services.frontend.src.pages.login.login",
                return_value=None,
            ),
            patch("services.frontend.src.pages.login.set_authenticated_session") as mock_set_session,
            patch.object(st, "error", side_effect=lambda msg: messages.append(msg)),
            patch.object(st, "rerun") as mock_rerun,
        ):
            login_page()

    assert "Invalid username or password." in messages
    mock_set_session.assert_not_called()
    mock_rerun.assert_not_called()


def test_login_page_empty_credentials() -> None:
    """Test empty inputs show a prompt and never call login."""

    messages = []
    with _widget_stacks(username=""):
        with (
            patch("services.frontend.src.pages.login.login") as mock_login,
            patch("services.frontend.src.pages.login.set_authenticated_session") as mock_set_session,
            patch.object(st, "error", side_effect=lambda msg: messages.append(msg)),
            patch.object(st, "rerun") as mock_rerun,
        ):
            login_page()

    assert "Please enter both username and password." in messages
    mock_login.assert_not_called()
    mock_set_session.assert_not_called()
    mock_rerun.assert_not_called()


def test_login_page_not_submitted() -> None:
    """Test that nothing happens when the form is not submitted."""

    messages = []
    with _widget_stacks(submitted=False):
        with (
            patch.object(st, "error", side_effect=lambda msg: messages.append(msg)),
            patch.object(st, "rerun") as mock_rerun,
        ):
            login_page()

    assert messages == []
    mock_rerun.assert_not_called()

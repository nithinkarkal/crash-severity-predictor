"""
Tests for session service
"""

from unittest.mock import MagicMock, patch

import streamlit as st

from services.frontend.src.services.session_service import (
    COOKIE_NAME,
    _extract_token,
    _safe_remove_cookie,
    clear_authenticated_session,
    get_role_from_token,
    initialize_session,
    is_admin,
    is_authenticated,
    is_data_scientist,
    request_page,
    set_authenticated_session,
)


def test_extract_token_empty() -> None:
    """Test extracting token from an empty cookie value."""

    assert _extract_token("") is None


def test_extract_token_plain_value() -> None:
    """Test extracting a plain token cookie value."""

    assert _extract_token("raw-token") == "raw-token"


def test_extract_token_legacy_json_value() -> None:
    """Test extracting a token from a legacy dict-encoded cookie."""

    assert _extract_token('{"value": "legacy-token"}') == "legacy-token"


def test_extract_token_legacy_json_non_string_value() -> None:
    """Test that a non-string legacy cookie value is rejected."""

    assert _extract_token('{"value": 42}') is None


def test_extract_token_invalid_json() -> None:
    """Test that malformed legacy cookies return no token."""

    assert _extract_token('{"value":') is None


def test_extract_token_legacy_json_missing_value() -> None:
    """Test that legacy cookies without a value key are rejected."""

    assert _extract_token('{"other": "x"}') is None


def test_set_authenticated_session_with_remember_me() -> None:
    """Test that remember-me persists the token in a cookie."""

    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYWRtaW4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    with (
        patch.object(st, "session_state") as mock_session,
        patch("services.frontend.src.services.session_service.CookieController") as mock_controller_cls,
    ):
        controller = mock_controller_cls.return_value
        controller.get.return_value = None

        set_authenticated_session(token, "test-user", True)

        assert mock_session.remember_me is True
        controller.set.assert_called_once()
        controller.remove.assert_not_called()


def test_set_authenticated_session_without_remember_me() -> None:
    """Test that non-persistent logins remove any stale cookie."""

    with (
        patch.object(st, "session_state") as mock_session,
        patch("services.frontend.src.services.session_service.CookieController") as mock_controller_cls,
    ):
        controller = mock_controller_cls.return_value
        controller.get.return_value = "stale-token"

        set_authenticated_session("new-token", "test-user", False)

        assert mock_session.remember_me is False
        controller.remove.assert_called_once_with(COOKIE_NAME)


def test_safe_remove_cookie_when_absent() -> None:
    """Test that removal is skipped when the cookie does not exist."""

    with patch("services.frontend.src.services.session_service.CookieController") as mock_controller_cls:
        controller = mock_controller_cls.return_value
        controller.get.return_value = None

        _safe_remove_cookie()

        controller.remove.assert_not_called()


def test_initialize_session_restores_cookie_token() -> None:
    """Test that a valid cookie token restores the session."""

    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYWRtaW4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    with (
        patch.object(st, "session_state") as mock_session,
        patch.object(st, "context") as mock_context,
        patch(
            "services.frontend.src.services.session_service.get_role_from_token",
            return_value="admin",
        ) as mock_role,
    ):
        mock_session.setdefault.side_effect = lambda key, value: setattr(mock_session, key, value)
        mock_session.authenticated = False
        mock_context.cookies = {COOKIE_NAME: token}

        initialize_session()

        mock_role.assert_called_once_with(token)
        assert mock_session.authenticated is True
        assert mock_session.token == token
        assert mock_session.role == "admin"
        assert mock_session.remember_me is True


def test_initialize_session_rejects_invalid_cookie_token() -> None:
    """Test that cookies with an unusable token are removed."""

    with (
        patch.object(st, "session_state") as mock_session,
        patch.object(st, "context") as mock_context,
        patch(
            "services.frontend.src.services.session_service.get_role_from_token",
            return_value=None,
        ),
        patch("services.frontend.src.services.session_service._safe_remove_cookie") as mock_remove,
    ):
        mock_session.setdefault.side_effect = lambda key, value: setattr(mock_session, key, value)
        mock_session.authenticated = False
        mock_context.cookies = {COOKIE_NAME: "invalid-token"}

        initialize_session()

        assert mock_session.authenticated is False
        mock_remove.assert_called_once()


def test_initialize_session_without_cookie() -> None:
    """Test initialization when no cookie is present."""

    with (
        patch.object(st, "session_state") as mock_session,
        patch.object(st, "context") as mock_context,
        patch(
            "services.frontend.src.services.session_service._safe_remove_cookie",
        ) as mock_remove,
    ):
        mock_session.setdefault.side_effect = lambda key, value: setattr(mock_session, key, value)
        mock_session.authenticated = False
        mock_context.cookies = {}

        initialize_session()

        assert mock_session.authenticated is False
        mock_remove.assert_not_called()


def test_initialize_session_already_authenticated() -> None:
    """Test that an existing session is left untouched."""

    with (
        patch.object(st, "session_state") as mock_session,
        patch.object(st, "context") as mock_context,
    ):
        # Treat all keys as already present so setdefault() does not
        # clobber the pre-existing authentication state we want to
        # preserve.
        mock_session.setdefault = MagicMock()
        mock_session.authenticated = True
        mock_session.token = "existing-token"

        initialize_session()

        assert mock_session.authenticated is True
        assert mock_session.token == "existing-token"
        mock_context.cookies.get.assert_not_called()


def test_get_role_from_token_bad_payload_encoding() -> None:
    """Test that undecodable JWT payloads return no role."""

    result = get_role_from_token("header.!!!invalid-base64!!!.signature")

    assert result is None


def test_initialize_session() -> None:
    """Test session initialization."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.setdefault.side_effect = lambda key, value: setattr(mock_session, key, value)

        initialize_session()

        expected_defaults = {
            "page": "Home",
            "authenticated": False,
            "token": None,
            "username": None,
            "role": None,
            "remember_me": False,
            "post_login_page": "Home",
            "prediction_result": None,
        }

        for key, value in expected_defaults.items():
            assert getattr(mock_session, key) == value


def test_set_authenticated_session() -> None:
    """Test setting authenticated session."""

    with patch.object(st, "session_state") as mock_session:
        # Mock the get_role_from_token function
        with patch("services.frontend.src.services.session_service.get_role_from_token", return_value="admin"):
            set_authenticated_session("test-token", "test-user", True)

            assert mock_session.authenticated is True
            assert mock_session.token == "test-token"
            assert mock_session.username == "test-user"
            assert mock_session.remember_me is True
            assert mock_session.role == "admin"


def test_clear_authenticated_session() -> None:
    """Test clearing authenticated session."""

    with patch.object(st, "session_state") as mock_session:
        # Set some initial values
        mock_session.authenticated = True
        mock_session.token = "test-token"
        mock_session.username = "test-user"
        mock_session.role = "admin"

        clear_authenticated_session()

        assert mock_session.authenticated is False
        assert mock_session.token is None
        assert mock_session.username is None
        assert mock_session.role is None
        assert mock_session.remember_me is False
        assert mock_session.post_login_page == "Home"
        assert mock_session.prediction_result is None
        assert mock_session.page == "Home"


def test_get_role_from_token_valid() -> None:
    """Test getting role from valid token."""

    # Valid JWT token with role claim
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYWRtaW4ifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

    result = get_role_from_token(token)
    assert result == "admin"


def test_get_role_from_token_invalid() -> None:
    """Test getting role from invalid token."""

    # Invalid token format
    result = get_role_from_token("invalid-token")
    assert result is None

    # Empty token
    result = get_role_from_token(None)
    assert result is None


def test_is_authenticated_true() -> None:
    """Test is_authenticated when authenticated."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": True, "token": "test-token"}.get(key, default)

        assert is_authenticated() is True


def test_is_authenticated_false() -> None:
    """Test is_authenticated when not authenticated."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": False, "token": None}.get(key, default)

        assert is_authenticated() is False


def test_is_admin_true() -> None:
    """Test is_admin when user is admin."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": True, "token": "test-token", "role": "admin"}.get(key, default)

        assert is_admin() is True


def test_is_admin_false() -> None:
    """Test is_admin when user is not admin."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": True, "token": "test-token", "role": "user"}.get(key, default)

        assert is_admin() is False


def test_is_data_scientist_true() -> None:
    """Test is_data_scientist when user is a user."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": True, "token": "test-token", "role": "user"}.get(key, default)

        assert is_data_scientist() is True


def test_is_data_scientist_false() -> None:
    """Test is_data_scientist when user is not a user."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": True, "token": "test-token", "role": "admin"}.get(key, default)

        assert is_data_scientist() is False


def test_request_page_unauthenticated_protected() -> None:
    """Test requesting protected page when not authenticated."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": False}.get(key, default)

        request_page("Prediction")

        assert mock_session.post_login_page == "Prediction"
        assert mock_session.page == "Login"


def test_request_page_authenticated_protected() -> None:
    """Test requesting protected page when authenticated."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": True, "token": "test-token"}.get(key, default)

        request_page("Prediction")

        assert mock_session.page == "Prediction"


def test_request_page_public() -> None:
    """Test requesting public page."""

    with patch.object(st, "session_state") as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {"authenticated": False}.get(key, default)

        request_page("Home")

        assert mock_session.page == "Home"

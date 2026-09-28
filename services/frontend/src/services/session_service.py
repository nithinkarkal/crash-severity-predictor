"""Frontend authentication session helpers."""

from __future__ import annotations

import base64
import binascii
import json

import streamlit as st
from streamlit_cookies_controller import CookieController

COOKIE_NAME = "asp_remember_token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def _cookies() -> CookieController:
    return CookieController()


def _safe_remove_cookie() -> None:
    """Remove the persistent cookie only if it exists."""
    cookies = _cookies()
    if cookies.get(COOKIE_NAME) is not None:
        cookies.remove(COOKIE_NAME)


def _extract_token(raw: str) -> str | None:
    """Handle legacy dict-encoded cookies and plain tokens."""
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            value = json.loads(raw).get("value")
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, str) else None
    return raw


def initialize_session() -> None:
    """Initialize frontend session state and restore persistent authentication."""

    defaults = {
        "page": "Home",
        "authenticated": False,
        "token": None,
        "username": None,
        "role": None,
        "remember_me": False,
        "post_login_page": "Home",
        "prediction_result": None,
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    if st.session_state.authenticated:
        return

    # Read cookie directly from the HTTP request instant, no JS delay.
    raw = st.context.cookies.get(COOKIE_NAME)
    token = _extract_token(raw) if raw else None

    if not token:
        return

    role = get_role_from_token(token)

    if role is None:
        _safe_remove_cookie()
        return

    st.session_state.authenticated = True
    st.session_state.token = token
    st.session_state.role = role
    st.session_state.remember_me = True


def set_authenticated_session(
    token: str,
    username: str,
    remember_me: bool = False,
) -> None:
    """Store authentication information in the Streamlit session."""

    st.session_state.authenticated = True
    st.session_state.token = token
    st.session_state.username = username
    st.session_state.role = get_role_from_token(token)
    st.session_state.remember_me = remember_me

    if remember_me:
        _cookies().set(
            COOKIE_NAME,
            token,
            max_age=COOKIE_MAX_AGE,
            path="/",
            same_site="lax",
        )
    else:
        _safe_remove_cookie()


def clear_authenticated_session() -> None:
    """Clear authentication state and remove persistent authentication."""

    st.session_state.authenticated = False
    st.session_state.token = None
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.remember_me = False
    st.session_state.prediction_result = None
    st.session_state.page = "Home"
    st.session_state.post_login_page = "Home"

    _safe_remove_cookie()


def get_role_from_token(token: str | None) -> str | None:
    """
    Read the role claim from the JWT.

    This is used only for frontend navigation visibility.
    Backend authorization remains authoritative.
    """

    if not token:
        return None

    try:
        parts = token.split(".")

        if len(parts) != 3:
            return None

        payload = parts[1]

        padding = "=" * (-len(payload) % 4)

        decoded = base64.urlsafe_b64decode(
            payload + padding,
        )

        claims = json.loads(
            decoded.decode("utf-8"),
        )

        role = claims.get("role")

        if isinstance(role, str):
            return role

    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ):
        return None

    return None


def is_authenticated() -> bool:
    """Return whether the current session is authenticated."""

    return bool(st.session_state.get("authenticated", False))


def is_admin() -> bool:
    """Return whether the current user has the admin role."""

    return is_authenticated() and st.session_state.get("role") == "admin"


def is_data_scientist() -> bool:
    """Return whether the current user has the standard user role."""

    return is_authenticated() and st.session_state.get("role") == "user"


def request_page(page: str) -> None:
    """
    Request navigation to a page.

    Protected pages remember the requested destination so that
    successful login can return the user directly to that page.
    """

    protected_pages = {
        "Prediction",
        "Model Insights",
        "Monitoring",
    }

    if page in protected_pages and not is_authenticated():
        st.session_state.post_login_page = page
        st.session_state.page = "Login"
        return

    st.session_state.page = page

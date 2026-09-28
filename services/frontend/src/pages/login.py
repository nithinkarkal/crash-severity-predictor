"""ASP login page."""

import streamlit as st

from services.frontend.src.services.auth_service import login
from services.frontend.src.services.session_service import (
    set_authenticated_session,
)


def login_page() -> None:
    """render the login page."""

    left, center, right = st.columns([1, 1.15, 1])

    with center:
        st.html(
            """
            <div class="asp-login-brand">
                <div class="asp-login-logo">ASP</div>
                <div class="asp-login-title">
                    Accident Severity<br>Predictor
                </div>
            </div>

            <div class="asp-login-heading">
                Welcome back!
            </div>

            <div class="asp-login-subtitle">
                Please sign in to continue
            </div>
            """
        )

        with st.form("login_form"):
            username = st.text_input(
                "Username",
                placeholder="Enter your username",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            remember = st.checkbox("Remember me")

            submitted = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

        if submitted:
            if not username or not password:
                st.error("Please enter both username and password.")
                return

            token = login(username, password)

            if token is None:
                st.error("Invalid username or password.")
                return

            set_authenticated_session(
                token=token.access_token,
                username=username,
                remember_me=remember,
            )

            target_page = st.session_state.get(
                "post_login_page",
                "Home",
            )

            st.session_state.post_login_page = "Home"
            st.session_state.page = target_page

            st.rerun()

        st.html(
            """
            <div class="asp-login-footer">
                ASP v1.0.0<br>
                Capstone Project · DataScientest · 2026
            </div>
            """
        )
